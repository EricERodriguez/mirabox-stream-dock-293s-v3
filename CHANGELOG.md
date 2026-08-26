# Changelog

## 1.0.1

Fixes for real hardware behavior found while migrating a working personal
integration to this daemon and validating it on the physical dock.

- **Fix: key icons never appeared** (right-side displays worked fine). The
  bridge only called `set_device()` + `wakeScreen()` + `set_brightness()` at
  startup. The official SDK's own reference program (`Python-SDK/src/main.py`
  in `MiraboxSpace/StreamDock-Device-SDK`) always calls `device.init()`
  instead, which additionally runs `clearAllIcon()` and an initial
  `refresh()` before any key image is drawn. Without `clearAllIcon()`, the
  15-key image pipeline silently ignored new images while commands kept
  firing normally and the independent side-display pipeline kept working —
  `app/daemon.py` now calls `device.init()` plus a short settle delay.
- **Fix: icons flashed briefly on a key press, then vanished; only the last
  keys processed (11-15) ever stuck, inconsistently.** `draw_page()` was
  pushing all 15 key images, then the 3 side images, then a single
  `refresh()`, with zero delay between writes. This dock's firmware cannot
  keep up with that rate: earlier writes get silently dropped, and only
  the writes closest in time to the final `refresh()` sometimes land — which
  is exactly keys 11-15, the last ones `POSITIONS` iterates over. Added a
  `KEY_WRITE_DELAY` (150 ms) pause after every `set_key_image()` call,
  including the periodic 5 s right-side-display refresh.
- **Fix: pressing a page-navigation key (11/15) sometimes turned off the
  device screen instead of paging.** The official SDK fires the key
  callback from its own internal HID reader thread and documents that the
  callback must be thread-safe. `on_key` used to call `draw_page()` (15+
  device writes) directly from that thread. It now only flags a pending
  redraw; the main thread (already polling every 0.2 s for the side
  displays) performs the actual redraw, exactly like the always-correct
  initial draw at startup.
- Noted but out of scope for this daemon: a physical unplug/replug leaves a
  running daemon holding a stale device handle (`hid_write ... No such
  device` in the log) until the service is restarted — restart the service,
  or use **Save and apply** in the editor, after reconnecting the dock.

## 1.0.0

Initial public release: GTK4 editor, official-SDK bridge, unlimited pages
with physical keys 11/15 as Previous/Next, three configurable right-side
displays, native 854×480 per-page background, `install.sh`, and
`scripts/package.sh` for tarball/`.deb` packaging.
