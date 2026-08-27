# Mirabox Stream Dock 293S V3 for Linux

A small, native Linux editor and official-SDK bridge for the **Mirabox Stream
Dock 293S V3**. It is designed for the 15-key model with three LCD displays on
the right side.

It offers a clean GTK editor for button labels, commands and images, multiple
pages, three configurable right-side displays, and the device's real LCD
background. The bridge never flashes firmware and contains no firmware-update
code.

![License: MIT](https://img.shields.io/badge/License-MIT-0ea5e9.svg)
![Platform: Linux](https://img.shields.io/badge/platform-Linux-172554.svg)

## Hardware compatibility

This project targets the model reported by the official Mirabox Linux SDK as
`StreamDock293sV3`:

| Property | Value |
| --- | --- |
| USB identity | `6603:1014` (`HOTSPOTEKUSB HID DEMO`) |
| Main controls | 15 LCD keys, 5 columns × 3 rows |
| Right side | 3 secondary LCD displays |
| Supported driver | [Mirabox StreamDock Device SDK](https://github.com/MiraboxSpace/StreamDock-Device-SDK) |

Do not use a generic Stream Deck driver or firmware intended for another
Mirabox product. In particular, this project does not support `MBox-N1`
firmware.

## What it does

- Shows a true 5×3 representation of the physical device in a GTK4 editor.
- Saves each key's label, shell command and optional PNG/JPEG image.
- Draws a readable label image for keys without an icon.
- Shows selected key images directly in the editor grid.
- Lets the user open or save a profile at any JSON path.
- Supports unlimited pages; physical keys 11 and 15 are Previous/Next by
  default and cycle through the configured pages.
- Drives the three right-side displays with clock, CPU, RAM or custom text.
- Sets the 293S V3's native 854 × 480 LCD background per page.
- Runs as a user service, so actions keep working after logging in.
- Uses the official Mirabox SDK for all device operations.

## Project layout

```
app/
  profile_store.py        Profile schema, migration, load/save, active-profile settings.
  daemon/                 The official-SDK bridge (installed as a systemd --user service).
    device.py               DeviceConnection: the one HID handle, with per-write pacing baked in.
    rendering.py            Pure image generation for keys/side displays/background, /proc readers.
    page_controller.py      PageController: page state, redraws, and reacting to key presses.
    __main__.py              Entrypoint (`python -m daemon`); wires the above together.
  editor/                 The GTK4 configuration editor.
    editor_controller.py    EditorState: profile state and editing rules, no GTK involved.
    main_window.py           The window: builds every widget and wires it to EditorState.
    key_widgets.py           Builds a key button's content (icon thumbnail vs. number/label).
    styles.py                The editor's CSS.
    app.py                   The Gtk.Application; __main__.py runs it as `python -m editor`.
```

Both `daemon` and `editor` are run with `app/` as the working directory, so
they can import the sibling `profile_store` module directly.

## Requirements

- Linux with a graphical GTK4 session.
- Python 3 with `venv` support.
- `git` and internet access during installation, to fetch the official SDK.
- A connected Mirabox Stream Dock 293S V3.

On Ubuntu, install the GTK and image prerequisites if they are not already
present:

```sh
sudo apt install python3-venv python3-gi gir1.2-gtk-4.0 python3-pil
```

## Install

```sh
git clone https://github.com/YOUR-ACCOUNT/mirabox-stream-dock-293s-v3.git
cd mirabox-stream-dock-293s-v3
./install.sh
```

The installer copies the application to your user data directory, creates the
profile at `~/.config/mirabox-stream-dock-293s-v3/profile.json`, and enables a
user service. It deliberately does not install a system rule without your
permission. Run the exact `sudo` commands printed by the installer once, then
reconnect the dock if necessary.

Open **Mirabox Stream Dock 293S V3** from the Applications menu after install.

### Migrating from another local integration

Only one process can control the dock. If an older service is already managing
the 293S V3, this installer stops before it enables the new bridge. First save
the old profile with **Open** then **Save as** into a new JSON file (for example
inside your personal ubuntu-config repository). Once you have verified that
copy, disable the older service yourself and run this installer again.

## Install from a package

`scripts/package.sh` builds a reproducible tarball, and a `.deb` when
`dpkg-deb` is available, under `dist/`. Neither package vendors the official
SDK: it is always fetched separately by `install.sh`, as documented above.

### Tarball

```sh
tar -xzf mirabox-stream-dock-293s-v3-VERSION.tar.gz
cd mirabox-stream-dock-293s-v3-VERSION
sha256sum -c mirabox-stream-dock-293s-v3-VERSION.tar.gz.sha256   # optional, verify integrity
./install.sh
```

### .deb

```sh
sha256sum -c mirabox-stream-dock-293s-v3_VERSION_all.deb.sha256   # optional, verify integrity
sudo dpkg -i mirabox-stream-dock-293s-v3_VERSION_all.deb
```

Installing the `.deb` needs `sudo` only to place files under
`/usr/share/mirabox-stream-dock-293s-v3`. It deliberately does not run
`install.sh` for you: the actual per-user setup (Python venv, fetching the
official SDK, enabling the `systemd --user` service) must run as your own
user, never as root. After installing the `.deb`, finish the setup by running,
as your normal user:

```sh
/usr/share/mirabox-stream-dock-293s-v3/install.sh
```

## Use the editor

1. Use **Open** to load a profile or **Save as** to choose its location. A
   personal repository such as `ubuntu-config` is a good place to keep your
   own profile; the application remembers the selected location.
2. Select a key in the 5×3 layout. Give it a label. A command is optional; an
   empty command leaves a display-only key.
3. Optionally choose a PNG or JPEG key image. **96 × 96 px** is the native key
   size and gives the sharpest result. Larger images are converted by the
   official SDK; the selected image is previewed on the editor button.
4. Use **Add page** for additional layouts. Key **11** goes to the previous
   page and key **15** goes to the next page by default, leaving 13 action keys
   per page. Those navigation keys wrap from first to last page and back.
5. Set each right-side display to **clock**, **CPU**, **RAM**, or **text**.
   Their native size is **80 × 80 px**.
6. Optionally choose a page background. The dock's supported LCD background is
   **854 × 480 px**; use a PNG or JPEG at exactly that size for no scaling.
7. Choose **Save and apply**.

The initial one-page schema is migrated when opened. If importing a profile
from another controller, use **Save as** to write a new public-project profile
instead of overwriting the source until you no longer use that controller.

The editor writes only your per-user profile and restarts the dedicated user
service. It does not reset, clear, or update the dock firmware.

## Troubleshooting

```sh
systemctl --user status mirabox-stream-dock-293s-v3.service
tail -f ~/.local/state/mirabox-stream-dock-293s-v3/daemon.log
```

If the service says it cannot find one device, reconnect the dock and verify
that the udev rule was installed. This project expects one connected 293S V3.

### Screen turns off when you press a key after a reconnect

This dock does not notify the daemon when it is unplugged and replugged, so a
running daemon can be left holding a stale handle to a device that no longer
exists. Until something re-opens the dock, its own firmware can toggle the
screen off on a keypress instead of running your action. Restart the bridge
after reconnecting the dock:

```sh
systemctl --user restart mirabox-stream-dock-293s-v3.service
```

Using **Save and apply** in the editor does this restart for you.

### Key icons are missing or only flash while a key is held

Both are fixed in this version, but are documented here in case you are
running an older copy of the daemon or hit a similar issue on a different
Mirabox model:

- **All 15 key icons missing, only the 3 right-side displays work**: the
  bridge must call the official SDK's `device.init()` before drawing
  anything. `init()` does more than `set_device()` + `wakeScreen()` +
  `set_brightness()`; it also runs `clearAllIcon()` and an initial
  `refresh()`. Skipping `clearAllIcon()` leaves the 15-key image pipeline in
  a state where new key images are silently ignored, while the independent
  side-display pipeline keeps working — matching commands that still fire
  with no icon ever appearing.
- **Icons flash briefly then disappear, and only the last few keys (11-15)
  ever stick**: this dock's firmware cannot absorb ~18 back-to-back key-image
  writes with no pause; earlier writes get silently dropped while only the
  last ones (closest to the final `refresh()`) sometimes land. The fix is a
  short `time.sleep()` (`KEY_WRITE_DELAY` in `app/daemon/device.py`) after
  every single `set_key_image()` call, on every full-page redraw and on the
  periodic right-side refresh alike.

### "Open…" or a "Choose…" button does nothing, or occasionally crashes the editor

Fixed in this version. `Gtk.FileChooserNative` is not kept alive by GTK on
its own once the function that created it returns; PyGObject can garbage
collect it while the native (portal) dialog is still opening, which showed
up as the dialog silently never appearing (spamming `Gtk-CRITICAL
**: thaw_updates: assertion 'GTK_IS_FILE_SYSTEM_MODEL (model)' failed` in
the terminal) or, less predictably, crashing the process outright. The
window now keeps an explicit reference (`self._active_dialog`) for as long
as the dialog is open.

See `CHANGELOG.md` for exactly what changed.

## License and SDK

The application code in this repository is licensed under [MIT](LICENSE).
Installation fetches the official Mirabox Device SDK separately; that SDK
remains subject to its own upstream license and terms.
