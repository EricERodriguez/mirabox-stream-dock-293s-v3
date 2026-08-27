"""The single connection this daemon process has to the physical dock.

There is exactly one Mirabox Stream Dock 293S V3 per daemon: this class
exists so every other module talks to "the device" through one object,
instead of passing the raw SDK handle (and its HID-timing quirks) around.
"""

from __future__ import annotations

import time

from StreamDock.DeviceManager import DeviceManager

# This dock's own firmware originally appeared to need real time to absorb
# each key image over HID -- sending all ~18 back-to-back with no pause left
# only the last few keys (11-15) showing an icon, with the rest silently
# dropped. Once BACKGROUND_WRITE_DELAY below was added and device.init()
# properly cleared every key slot first, that per-key pacing turned out to
# be unnecessary: 0 was found stable through extensive manual, human-in-the-
# loop testing on the real dock (15 keys, both pages, repeated page changes,
# waited out for the delayed-fade failure mode BACKGROUND_WRITE_DELAY
# documents below). Values in between (0.08-0.135) failed non-monotonically
# during that same testing, which points to real timing noise elsewhere
# (USB scheduling, the SDK's own transfer state, etc.) rather than a clean
# threshold -- so if key icons start dropping again on different hardware or
# after an SDK update, re-introducing a small pause here is the first thing
# to try, and re-verify with the same rigor (all 15 keys, both pages,
# waited out, repeated) before trusting a single quick look.
KEY_WRITE_DELAY = 0

# The 854x480 background is a much larger transfer than a 96x96/80x80 key
# image -- large enough that a real (non-solid-color) photo takes noticeably
# longer to absorb than a short pause accounts for. When that transfer was
# still busy, the device would let the following key-image writes render
# briefly and then silently revert them later (keys 1-6, then 1-3, then 1-7
# depending on the value tried, going blank ~15-20s after an otherwise
# perfect page draw) -- a delayed failure mode, not an immediate one, easy
# to miss on a quick look. This delay also applies to every page redraw, not
# just pages with a real background: the blank-background fallback goes
# through the exact same device call. 1.4 is the lowest value that held up
# across repeated, deliberately-delayed manual checks (15-20s+ per page, all
# 15 keys, both pages, several rounds) after values as low as 0.2 initially
# looked fine but failed once actually waited out.
BACKGROUND_WRITE_DELAY = 1.4


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
