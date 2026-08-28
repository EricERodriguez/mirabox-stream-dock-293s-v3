"""Pure image-generation helpers for the dock's key, side-display, and
touchscreen-background artwork, plus the /proc readers that feed them.

Nothing in this module touches the device: it only ever writes PNG/JPEG
files under STATE_HOME and returns their path.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "mirabox-stream-dock-293s-v3"
SIDE_KEYS = (16, 17, 18)


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
    except OSError:
        return ImageFont.load_default()


def centered(draw: ImageDraw.ImageDraw, image: Image.Image, text: str, y: int, text_font, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=text_font)
    draw.text(((image.width - (box[2] - box[0])) / 2, y), text, font=text_font, fill=fill)


def key_tile(number: int, label: str) -> Image.Image:
    """The generated tile a key shows when it has no icon: rounded border,
    physical number, label. Also the "background" an icon fades toward as
    its opacity drops, so lowering opacity reveals this instead of a flat
    color -- exactly what the key would look like with the icon removed.
    """
    image = Image.new("RGB", (96, 96), "#0f172a")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 93, 93), radius=12, outline="#334155", width=2)
    centered(draw, image, str(number), 14, font(13), "#94a3b8")
    words = label.strip().split() or [f"Key {number}"]
    lines = (" ".join(words[:2]), " ".join(words[2:4]))
    y = 38 if not lines[1] else 32
    centered(draw, image, lines[0][:12], y, font(15, bold=True), "#f8fafc")
    if lines[1]:
        centered(draw, image, lines[1][:12], y + 19, font(12), "#cbd5e1")
    return image


def render_key(number: int, label: str) -> Path:
    target = STATE_HOME / f"key-{number}.png"
    key_tile(number, label).save(target)
    return target


def read_cpu_percent(previous: tuple[int, int] | None) -> tuple[float, tuple[int, int]]:
    values = [int(value) for value in Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]]
    total, idle = sum(values), values[3] + (values[4] if len(values) > 4 else 0)
    if previous is None:
        return 0.0, (total, idle)
    total_delta, idle_delta = total - previous[0], idle - previous[1]
    value = 0.0 if total_delta <= 0 else 100 * (1 - idle_delta / total_delta)
    return max(0.0, min(100.0, value)), (total, idle)


def read_ram_percent() -> float:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", maxsplit=1)
        values[key] = int(value.split()[0])
    return 100 * (1 - values.get("MemAvailable", values["MemFree"]) / values["MemTotal"])


def read_vpn_connected() -> bool:
    """Best-effort detection of the ipsec-rentasweb tunnel, mirroring the
    heuristic already trusted in ubuntu-config's yakuake system-hud.sh:
    tunnel interfaces, VPN-assigned addresses, or routes for them. Skips the
    sudo-gated `ipsec statusall` check that script also has, since this runs
    unattended every refresh cycle.
    """
    def out(*args: str) -> str:
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout
        except Exception:
            return ""

    ip_addr = out("ip", "a")
    if re.search(r"\b(tun0|wg0|ppp0|ipsec0)\b", ip_addr) or re.search(r"\b10\.(48|42)\.", ip_addr):
        return True
    if re.search(r"\b10\.(48|42)\.", out("ip", "route", "show", "table", "all")):
        return True
    return bool(out("ip", "xfrm", "state").strip())


def side_text(spec: dict, cpu: float) -> tuple[str, str]:
    mode = spec.get("mode", "text")
    if mode == "clock":
        return time.strftime("%H:%M"), time.strftime("%d %b")
    if mode == "cpu":
        return f"{cpu:.0f}%", "CPU"
    if mode == "ram":
        return f"{read_ram_percent():.0f}%", "RAM"
    return str(spec.get("text", "Display"))[:10] or "Display", "CUSTOM"


def render_side(key: int, spec: dict, cpu: float, vpn_connected: bool) -> Path:
    image = Image.new("RGB", (80, 80), "#111827")
    draw = ImageDraw.Draw(image)
    # The border doubles as an ambient VPN indicator across all three side
    # displays -- there's no free fourth physical LCD to dedicate to it, so
    # this folds the signal into the ones that already exist instead of
    # displacing clock/CPU/RAM.
    outline = "#22c55e" if vpn_connected else "#ef4444"
    draw.rounded_rectangle((2, 2, 77, 77), radius=10, outline=outline, width=2)
    headline, caption = side_text(spec, cpu)
    centered(draw, image, headline, 20, font(23, bold=True), "#f8fafc")
    centered(draw, image, caption, 53, font(11), "#7dd3fc")
    target = STATE_HOME / f"side-{key}.png"
    image.save(target)
    return target


def crop_background(background: Image.Image, position: str) -> Image.Image:
    """The slice of the real touchscreen background that sits behind one
    key, assuming the 5x3 key grid tiles the full 854x480 panel edge to
    edge with no margins -- the 293S V3's keys and background live on the
    same touch panel, confirmed against the physical dock, but the exact
    per-key pixel offset isn't documented by the SDK, so this is a best
    guess: re-check alignment on the real hardware and adjust here if the
    revealed slice doesn't line up with what is actually behind the key.
    """
    x, y = (int(value) for value in position.split("x", maxsplit=1))
    cell_w, cell_h = background.width / 5, background.height / 3
    box = (round(x * cell_w), round(y * cell_h), round((x + 1) * cell_w), round((y + 1) * cell_h))
    return background.crop(box).resize((96, 96))


def render_icon(number: int, position: str, icon: Path, opacity: int, background: Image.Image) -> Path:
    """Fade ``icon`` toward the slice of the real touchscreen background
    behind this key, so lowering opacity reveals the dock's actual
    wallpaper there instead of a flat color or a generated tile.

    Only called when opacity < 100 -- at full opacity the icon file is sent
    to the device unchanged, exactly like before this existed.
    """
    backdrop = crop_background(background, position)
    source = Image.open(icon).convert("RGBA").resize(backdrop.size)
    flattened = Image.alpha_composite(backdrop.convert("RGBA"), source).convert("RGB")
    faded = Image.blend(backdrop.convert("RGB"), flattened, max(0.0, min(100, opacity)) / 100)
    target = STATE_HOME / f"key-{number}-icon.png"
    faded.save(target)
    return target


def render_blank_background() -> Path:
    target = STATE_HOME / "blank-background.jpg"
    Image.new("RGB", (854, 480), "#0f172a").save(target, "JPEG", quality=95)
    return target
