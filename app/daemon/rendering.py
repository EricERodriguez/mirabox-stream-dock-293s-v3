"""Pure image-generation helpers for the dock's key, side-display, and
touchscreen-background artwork, plus the /proc readers that feed them.

Nothing in this module touches the device: it only ever writes PNG/JPEG
files under STATE_HOME and returns their path.
"""

from __future__ import annotations

import os
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


def render_key(number: int, label: str) -> Path:
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
    target = STATE_HOME / f"key-{number}.png"
    image.save(target)
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


def side_text(spec: dict, cpu: float) -> tuple[str, str]:
    mode = spec.get("mode", "text")
    if mode == "clock":
        return time.strftime("%H:%M"), time.strftime("%d %b")
    if mode == "cpu":
        return f"{cpu:.0f}%", "CPU"
    if mode == "ram":
        return f"{read_ram_percent():.0f}%", "RAM"
    return str(spec.get("text", "Display"))[:10] or "Display", "CUSTOM"


def render_side(key: int, spec: dict, cpu: float) -> Path:
    image = Image.new("RGB", (80, 80), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 77, 77), radius=10, outline="#0ea5e9", width=2)
    headline, caption = side_text(spec, cpu)
    centered(draw, image, headline, 20, font(23, bold=True), "#f8fafc")
    centered(draw, image, caption, 53, font(11), "#7dd3fc")
    target = STATE_HOME / f"side-{key}.png"
    image.save(target)
    return target


def render_blank_background() -> Path:
    target = STATE_HOME / "blank-background.jpg"
    Image.new("RGB", (854, 480), "#0f172a").save(target, "JPEG", quality=95)
    return target
