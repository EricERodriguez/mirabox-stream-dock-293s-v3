#!/usr/bin/env python3
"""Official-SDK bridge for the Mirabox Stream Dock 293S V3.

The dock is USB 6603:1014 and is exposed by Mirabox's SDK as
``StreamDock293sV3``. This program only updates LCD images and runs commands
explicitly saved in the local profile; it contains no firmware functionality.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from StreamDock.DeviceManager import DeviceManager
from StreamDock.InputTypes import EventType

from profile_store import POSITIONS, active_profile_path, load_profile

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


def launch(command: str) -> None:
    logging.info("launching configured action: %s", command)
    subprocess.Popen(command, shell=True, executable="/bin/bash", stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def render_blank_background() -> Path:
    target = STATE_HOME / "blank-background.jpg"
    Image.new("RGB", (854, 480), "#0f172a").save(target, "JPEG", quality=95)
    return target


def main() -> int:
    STATE_HOME.mkdir(parents=True, exist_ok=True)
    os.chdir(STATE_HOME)
    logging.basicConfig(filename=STATE_HOME / "daemon.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    profile, profile_path = load_profile(active_profile_path())
    devices = DeviceManager().enumerate()
    if len(devices) != 1:
        raise RuntimeError(f"expected one Mirabox Stream Dock 293S V3, found {len(devices)}")
    device = devices[0]
    if not device.open():
        raise RuntimeError(f"could not open {device.path}")

    stopping = False
    def stop(*_args: object) -> None:
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        # device.init() (not just set_device()/wakeScreen()/set_brightness()) is what
        # the official SDK's own reference program calls before pushing any key image:
        # it also clears every key slot (clearAllIcon()) and refreshes once. Skipping
        # clearAllIcon() left the 15-key grid's image pipeline in a state where new key
        # images were silently ignored, while the independent side-display/background
        # paths kept working -- exactly the reported symptom (commands fire, icons don't).
        device.init()
        time.sleep(2)
        side = profile.get("side_displays", {})
        cpu, snapshot = read_cpu_percent(None)
        page_index = 0
        actions: dict[int, str] = {}
        roles: dict[int, str] = {}
        redraw_pending = False

        # This dock's own firmware appears to need real time to absorb each key
        # image over HID: sending all ~18 images back-to-back with no pause left
        # only the last few keys processed (11-15) showing an icon, with the rest
        # silently dropped. A short pause after every write gives it time to
        # actually commit each tile before the next one arrives.
        KEY_WRITE_DELAY = 0.15

        def draw_page() -> None:
            nonlocal actions, roles
            page = profile["pages"][page_index]
            background = Path(str(page.get("background_image", ""))).expanduser()
            device.set_touchscreen_image(str(background if background.is_file() else render_blank_background()))
            time.sleep(KEY_WRITE_DELAY)
            actions, roles = {}, {}
            for position in POSITIONS:
                definition = page["keys"][position]
                x, y = (int(value) for value in position.split("x", maxsplit=1))
                key = y * 5 + x + 1
                label = str(definition.get("label", f"Key {key}"))
                icon = Path(str(definition.get("icon", ""))).expanduser()
                device.set_key_image(key, str(icon if icon.is_file() else render_key(key, label)))
                time.sleep(KEY_WRITE_DELAY)
                role = str(definition.get("role", ""))
                if role in ("previous", "next"):
                    roles[key] = role
                else:
                    command = str(definition.get("command", "")).strip()
                    if command:
                        actions[key] = command
            for key in SIDE_KEYS:
                device.set_key_image(key, str(render_side(key, side.get(str(key), {}), cpu)))
                time.sleep(KEY_WRITE_DELAY)
            device.refresh()

        draw_page()

        def on_key(_device, event) -> None:
            # The official SDK fires this callback from its own HID reader thread and
            # documents that the callback must be thread-safe. Pushing 15+ key images
            # from that thread races the SDK's shared "Temporary.jpg" transfer file and
            # leaves keys blank, even though this function's own bookkeeping (page_index,
            # actions, roles) is unaffected. So this callback only flags a redraw; the
            # actual device image writes happen on the main thread below, exactly like
            # the initial draw_page() call at startup that always renders correctly.
            if event.event_type == EventType.BUTTON and event.state == 1 and event.key:
                nonlocal page_index, redraw_pending
                key = event.key.value
                role = roles.get(key)
                if role == "previous":
                    page_index = (page_index - 1) % len(profile["pages"])
                    redraw_pending = True
                    logging.info("switched to page %s via previous navigation", page_index + 1)
                    return
                if role == "next":
                    page_index = (page_index + 1) % len(profile["pages"])
                    redraw_pending = True
                    logging.info("switched to page %s via next navigation", page_index + 1)
                    return
                command = actions.get(key)
                if command:
                    launch(command)

        device.set_key_callback(on_key)
        logging.info("ready: %s page(s), 3 right-side displays, profile %s on %s", len(profile["pages"]), profile_path, device.path)
        next_refresh = time.monotonic() + 5
        while not stopping:
            if redraw_pending:
                redraw_pending = False
                draw_page()
            if time.monotonic() >= next_refresh:
                cpu, snapshot = read_cpu_percent(snapshot)
                for key in SIDE_KEYS:
                    device.set_key_image(key, str(render_side(key, side.get(str(key), {}), cpu)))
                    time.sleep(KEY_WRITE_DELAY)
                next_refresh = time.monotonic() + 5
            time.sleep(0.2)
    finally:
        device.close(notify=False)
        logging.info("stopped")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("fatal bridge error")
        raise
