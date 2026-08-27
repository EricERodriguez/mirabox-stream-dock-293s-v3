"""Ties the active profile, the device connection, and key/side rendering
together: draws pages and reacts to physical button presses.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from StreamDock.InputTypes import EventType

from profile_store import POSITIONS

from .device import DeviceConnection
from .rendering import SIDE_KEYS, render_blank_background, render_key, render_side


def launch(command: str) -> None:
    logging.info("launching configured action: %s", command)
    subprocess.Popen(command, shell=True, executable="/bin/bash", stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class PageController:
    """Owns page_index/actions/roles bookkeeping and all device redraws.

    draw_page() must only ever run on the main thread. The official SDK
    fires the key callback from its own internal HID reader thread and
    documents that the callback must be thread-safe. Pushing 15+ key image
    writes from that thread raced the SDK's own transfer state and left
    keys blank, even though this class's actions/roles bookkeeping (pure
    Python, no device I/O) was unaffected -- that's why on_key() only flags
    a pending redraw instead of drawing directly; the daemon's main loop is
    what actually calls draw_page(), exactly like the always-correct
    initial draw at startup.
    """

    def __init__(self, device: DeviceConnection, profile: dict) -> None:
        self.device = device
        self.profile = profile
        self.side = profile.get("side_displays", {})
        self.page_index = 0
        self.actions: dict[int, str] = {}
        self.roles: dict[int, str] = {}
        self.redraw_pending = False

    def draw_page(self, cpu: float) -> None:
        page = self.profile["pages"][self.page_index]
        background = Path(str(page.get("background_image", ""))).expanduser()
        self.device.set_touchscreen_image(str(background if background.is_file() else render_blank_background()))
        self.actions, self.roles = {}, {}
        for position in POSITIONS:
            definition = page["keys"][position]
            x, y = (int(value) for value in position.split("x", maxsplit=1))
            key = y * 5 + x + 1
            label = str(definition.get("label", f"Key {key}"))
            icon = Path(str(definition.get("icon", ""))).expanduser()
            self.device.set_key_image(key, str(icon if icon.is_file() else render_key(key, label)))
            role = str(definition.get("role", ""))
            if role in ("previous", "next"):
                self.roles[key] = role
            else:
                command = str(definition.get("command", "")).strip()
                if command:
                    self.actions[key] = command
        self.refresh_side_displays(cpu)
        self.device.refresh()

    def refresh_side_displays(self, cpu: float) -> None:
        for key in SIDE_KEYS:
            self.device.set_key_image(key, str(render_side(key, self.side.get(str(key), {}), cpu)))

    def on_key(self, _device, event) -> None:
        if event.event_type != EventType.BUTTON or event.state != 1 or not event.key:
            return
        key = event.key.value
        role = self.roles.get(key)
        if role == "previous":
            self.page_index = (self.page_index - 1) % len(self.profile["pages"])
            self.redraw_pending = True
            logging.info("switched to page %s via previous navigation", self.page_index + 1)
            return
        if role == "next":
            self.page_index = (self.page_index + 1) % len(self.profile["pages"])
            self.redraw_pending = True
            logging.info("switched to page %s via next navigation", self.page_index + 1)
            return
        command = self.actions.get(key)
        if command:
            launch(command)
