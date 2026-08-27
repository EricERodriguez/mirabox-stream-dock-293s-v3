"""The single connection this daemon process has to the physical dock.

There is exactly one Mirabox Stream Dock 293S V3 per daemon: this class
exists so every other module talks to "the device" through one object,
instead of passing the raw SDK handle (and its HID-timing quirks) around.
"""

from __future__ import annotations

import time

from StreamDock.DeviceManager import DeviceManager

# This dock's own firmware appears to need real time to absorb each key
# image over HID: sending all ~18 images back-to-back with no pause left
# only the last few keys processed (11-15) showing an icon, with the rest
# silently dropped. A short pause after every write gives it time to
# actually commit each tile before the next one arrives.
KEY_WRITE_DELAY = 0.15

# The 854x480 background is a much larger transfer than a 96x96/80x80 key
# image -- large enough that a real (non-solid-color) photo take noticeably
# longer to absorb than KEY_WRITE_DELAY accounts for. When that transfer was
# still busy, the device silently dropped the following key-image writes
# (keys 1-6 went blank while a background was set, matching the same
# silent-drop behavior KEY_WRITE_DELAY exists to avoid). Give the background
# write its own, much longer settle time before anything else is sent.
BACKGROUND_WRITE_DELAY = 1.5


class DeviceConnection:
    """Owns the one open handle to the dock and paces every image write."""

    def __init__(self) -> None:
        devices = DeviceManager().enumerate()
        if len(devices) != 1:
            raise RuntimeError(f"expected one Mirabox Stream Dock 293S V3, found {len(devices)}")
        self._device = devices[0]
        if not self._device.open():
            raise RuntimeError(f"could not open {self._device.path}")

    @property
    def path(self) -> str:
        return self._device.path

    def init(self) -> None:
        # device.init() (not just set_device()/wakeScreen()/set_brightness()) is what
        # the official SDK's own reference program calls before pushing any key image:
        # it also clears every key slot (clearAllIcon()) and refreshes once. Skipping
        # clearAllIcon() left the 15-key grid's image pipeline in a state where new key
        # images were silently ignored, while the independent side-display/background
        # paths kept working -- exactly the reported symptom (commands fire, icons don't).
        self._device.init()
        time.sleep(2)

    def set_touchscreen_image(self, path: str) -> None:
        self._device.set_touchscreen_image(path)
        time.sleep(BACKGROUND_WRITE_DELAY)

    def set_key_image(self, key: int, path: str) -> None:
        self._device.set_key_image(key, path)
        time.sleep(KEY_WRITE_DELAY)

    def refresh(self) -> None:
        self._device.refresh()

    def set_key_callback(self, callback) -> None:
        self._device.set_key_callback(callback)

    def close(self) -> None:
        self._device.close(notify=False)
