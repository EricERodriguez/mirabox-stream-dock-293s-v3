# Changelog

## 1.2.0

- **Added: "Use this background on every page" checkbox.** Backgrounds were
  strictly per-page; this new option shares one background across every page
  of a profile instead. New profile fields: top-level `shared_background`
  (bool) and `background_image` (the shared path), both defaulted by
  `profile_store.normalise()` for old profiles. New
  `profile_store.active_background(profile, page)` picks the right one
  (shared vs. per-page) and is used by both `app/daemon/page_controller.py`
  and the editor, so they can never disagree. In the editor
  (`app/editor/editor_controller.py` / `main_window.py`), toggling the
  checkbox persists whatever was typed into the mode you're leaving before
  switching, so no edit is silently lost.

## 1.1.2

- **Fix: setting a real page background made keys 1-6 lose their icon.**
  The 854×480 background is a far larger HID transfer than a 96×96/80×80
  key image; the fixed `render_blank_background()` fallback (a small,
  near-solid-color JPEG) absorbed fast enough that this never showed up,
  but a real photo/background took long enough to transfer that the
  following key-image writes landed while the device was still busy with
  it, and got silently dropped -- the same class of bug `KEY_WRITE_DELAY`
  exists to prevent, just for a much bigger payload. Added a separate,
  longer `BACKGROUND_WRITE_DELAY` (1.5s) after `set_touchscreen_image()`,
  in `app/daemon/device.py`.

## 1.1.1

- **Fix: "Open…" and the inspector's "Choose…" buttons did nothing, and
  sometimes crashed the editor.** Each `Gtk.FileChooserNative` was a local
  variable in the method that created it; nothing else kept it referenced,
  so PyGObject could garbage-collect the dialog while the portal-backed
  native dialog was still being set up. Observed as either the dialog never
  appearing (with `Gtk-CRITICAL **: thaw_updates: assertion
  'GTK_IS_FILE_SYSTEM_MODEL (model)' failed` spamming the terminal) or an
  outright crash with no traceback. `MainWindow` now stores the open dialog
  in `self._active_dialog` until its response handler destroys it.

## 1.1.0

Internal architecture refactor. No functional change: the same
`device.init()` sequence, `KEY_WRITE_DELAY` pacing, and main-thread-only
redraw from 1.0.1 are preserved exactly, just reorganized. Verified against
the real, physical dock (single-page and two-page profiles, `Save and
apply`) after the move, not just by re-running the test suite.

- `app/daemon.py` split into the `app/daemon/` package: `device.py`
  (`DeviceConnection`, owns the one HID handle and the write pacing),
  `rendering.py` (pure key/side/background image generation, `/proc`
  readers), `page_controller.py` (`PageController`: page state, redraws,
  reacting to key presses), and `__main__.py` (entrypoint). Run as
  `python -m daemon` with `app/` as the working directory.
- `app/editor.py` split into the `app/editor/` package: `editor_controller.py`
  (`EditorState`: profile state and editing rules, no GTK import),
  `main_window.py` (the window: widget tree, wired to `EditorState`),
  `key_widgets.py` (builds a key button's content — icon thumbnail vs.
  number/label), `styles.py` (the CSS), and `app.py` (the thin
  `Gtk.Application`). Run as `python -m editor`.
- `install.sh`, `scripts/package.sh`, the systemd unit (now sets
  `WorkingDirectory` and calls `python -m daemon`), and `launch-editor.sh`
  (now calls `python -m editor`) updated for the new package layout.
- No profile schema change; existing profiles keep working unmodified.

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
