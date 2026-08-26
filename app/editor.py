#!/usr/bin/env python3
"""GTK4 configuration editor for the Mirabox Stream Dock 293S V3."""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk

from profile_store import POSITIONS, load_profile, select_profile, write_json


APP_ID = "vip.key123.mirabox.StreamDock293SV3"
SERVICE = "mirabox-stream-dock-293s-v3.service"
SIDE_MODES = ("clock", "cpu", "ram", "text")

CSS = """
window { background: #111827; }
.hero { background: linear-gradient(120deg, #0f172a, #172554); padding: 22px 26px; }
.eyebrow { color: #7dd3fc; font-weight: 700; letter-spacing: .08em; }
.muted { color: #94a3b8; }
.profile-path { color: #cbd5e1; font-family: monospace; font-size: 12px; }
.deck-frame { background: #0b1220; border-radius: 16px; padding: 18px; }
.deck-key { background: #172033; border-radius: 12px; border: 1px solid #334155; min-width: 92px; min-height: 94px; }
.deck-key:hover { background: #1e293b; border-color: #64748b; }
.deck-key.active { background: #1d4ed8; border-color: #7dd3fc; box-shadow: 0 0 0 2px rgba(125,211,252,.35); }
.deck-key.navigation { border-color: #a78bfa; }
.side-card, .inspector-card { background: #172033; border: 1px solid #334155; border-radius: 12px; padding: 14px; }
.status-ok { color: #86efac; font-weight: 600; }
.status-error { color: #fca5a5; font-weight: 600; }
.key-number { color: #93c5fd; font-size: 12px; font-weight: 700; }
.key-name { color: #f8fafc; font-weight: 700; }
.thumbnail { border-radius: 6px; }
"""


class StreamDockEditor(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.profile: dict = {}
        self.profile_path = Path()
        self.page_index = 0
        self.selected = "0x0"
        self.key_buttons: dict[str, Gtk.Button] = {}
        self.side_modes: dict[str, Gtk.DropDown] = {}
        self.side_texts: dict[str, Gtk.Entry] = {}

    def do_activate(self) -> None:
        self.profile, self.profile_path = load_profile()
        self._install_css()
        window = Gtk.ApplicationWindow(application=self, title="Mirabox Stream Dock 293S V3")
        window.set_default_size(1220, 790)
        window.set_size_request(900, 620)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self._hero())
        root.append(self._profile_bar())
        content = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        content.set_wide_handle(True)
        content.set_start_child(self._deck_panel())
        content.set_end_child(self._inspector())
        content.set_resize_start_child(True)
        root.append(content)
        root.append(self._footer())
        window.set_child(root)
        self._select_key(self.selected)
        window.present()

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _hero(self) -> Gtk.Widget:
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, css_classes=["hero"])
        hero.append(Gtk.Label(label="MIRABOX · STREAM DOCK 293S V3", xalign=0, css_classes=["eyebrow"]))
        hero.append(Gtk.Label(label="Command center for your 15 keys", xalign=0, css_classes=["title-1"]))
        hero.append(Gtk.Label(label="Configure pages, images, LCD displays and the 854 × 480 device background.", xalign=0, wrap=True, css_classes=["muted"]))
        return hero

    def _profile_bar(self) -> Gtk.Widget:
        bar = Gtk.Box(spacing=8, margin_top=10, margin_bottom=8, margin_start=22, margin_end=22)
        bar.append(Gtk.Label(label="Profile", css_classes=["heading"]))
        self.profile_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=3, css_classes=["profile-path"])
        bar.append(self.profile_label)
        open_button = Gtk.Button(label="Open…")
        open_button.connect("clicked", self._open_profile)
        bar.append(open_button)
        save_as = Gtk.Button(label="Save as…")
        save_as.connect("clicked", self._save_as)
        bar.append(save_as)
        self._refresh_profile_label()
        return bar

    def _deck_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=10, margin_bottom=20, margin_start=22, margin_end=18)
        page_bar = Gtk.Box(spacing=8)
        page_bar.append(Gtk.Label(label="Device layout", xalign=0, css_classes=["title-3"]))
        page_bar.append(Gtk.Box(hexpand=True))
        previous = Gtk.Button(label="‹")
        previous.set_tooltip_text("Previous editor page")
        previous.connect("clicked", lambda _button: self._change_page(-1))
        page_bar.append(previous)
        self.page_indicator = Gtk.Label(css_classes=["heading"])
        page_bar.append(self.page_indicator)
        following = Gtk.Button(label="›")
        following.set_tooltip_text("Next editor page")
        following.connect("clicked", lambda _button: self._change_page(1))
        page_bar.append(following)
        add_page = Gtk.Button(label="Add page")
        add_page.connect("clicked", self._add_page)
        page_bar.append(add_page)
        self.remove_page = Gtk.Button(label="Remove")
        self.remove_page.connect("clicked", self._remove_page)
        page_bar.append(self.remove_page)
        panel.append(page_bar)
        panel.append(Gtk.Label(label="Keys 11 and 15 are Previous and Next by default. They cycle through pages on the physical dock.", xalign=0, wrap=True, css_classes=["muted"]))
        row = Gtk.Box(spacing=16, vexpand=True)
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["deck-frame"], vexpand=True, hexpand=True)
        grid = Gtk.Grid(row_spacing=9, column_spacing=9, hexpand=True, vexpand=True)
        for y in range(3):
            for x in range(5):
                position = f"{x}x{y}"
                button = Gtk.Button(vexpand=True, hexpand=True, css_classes=["deck-key"])
                button.set_size_request(94, 94)
                button.connect("clicked", lambda _button, item=position: self._select_key(item))
                self.key_buttons[position] = button
                grid.attach(button, x, y, 1, 1)
        frame.append(grid)
        row.append(frame)
        right_lcd = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        right_lcd.append(Gtk.Label(label="Right LCD", xalign=0, css_classes=["title-4"]))
        right_lcd.append(Gtk.Label(label="Three independent status displays", xalign=0, wrap=True, css_classes=["muted"]))
        for index, key in enumerate(("16", "17", "18"), start=1):
            right_lcd.append(self._side_card(key, index))
        row.append(right_lcd)
        panel.append(row)
        self._refresh_key_buttons()
        return panel

    def _side_card(self, key: str, number: int) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, css_classes=["side-card"])
        card.append(Gtk.Label(label=f"Display {number}", xalign=0, css_classes=["heading"]))
        mode = Gtk.DropDown.new_from_strings(SIDE_MODES)
        current = self.profile["side_displays"][key].get("mode", SIDE_MODES[number - 1])
        mode.set_selected(SIDE_MODES.index(current) if current in SIDE_MODES else 0)
        mode.connect("notify::selected", self._side_mode_changed, key)
        self.side_modes[key] = mode
        card.append(mode)
        text = Gtk.Entry(placeholder_text="Custom text")
        text.set_text(self.profile["side_displays"][key].get("text", ""))
        text.set_sensitive(current == "text")
        self.side_texts[key] = text
        card.append(text)
        return card

    def _side_mode_changed(self, dropdown: Gtk.DropDown, _value: object, key: str) -> None:
        self.side_texts[key].set_sensitive(SIDE_MODES[dropdown.get_selected()] == "text")

    def _load_side_widgets(self) -> None:
        for key, dropdown in self.side_modes.items():
            spec = self.profile["side_displays"][key]
            mode = spec.get("mode", "text")
            dropdown.set_selected(SIDE_MODES.index(mode) if mode in SIDE_MODES else 3)
            self.side_texts[key].set_text(spec.get("text", ""))
            self.side_texts[key].set_sensitive(mode == "text")

    def _inspector(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_width=350)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=20, margin_bottom=20, margin_start=18, margin_end=22)
        box.append(Gtk.Label(label="Key inspector", xalign=0, css_classes=["title-3"]))
        self.key_context = Gtk.Label(xalign=0, css_classes=["muted"])
        box.append(self.key_context)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9, css_classes=["inspector-card"])
        card.append(Gtk.Label(label="Label", xalign=0, css_classes=["heading"]))
        self.label_entry = Gtk.Entry(placeholder_text="e.g. Terminal")
        card.append(self.label_entry)
        card.append(Gtk.Label(label="Command", xalign=0, css_classes=["heading"]))
        self.command_entry = Gtk.Entry(placeholder_text="e.g. gnome-terminal")
        card.append(self.command_entry)
        self.command_help = Gtk.Label(xalign=0, wrap=True, css_classes=["muted"])
        card.append(self.command_help)
        card.append(Gtk.Label(label="Key image", xalign=0, css_classes=["heading"]))
        self.icon_entry = Gtk.Entry(placeholder_text="Optional PNG or JPEG, 96 × 96 recommended")
        icon_row = Gtk.Box(spacing=8)
        icon_row.append(self.icon_entry)
        choose_icon = Gtk.Button(label="Choose…")
        choose_icon.connect("clicked", self._choose_icon)
        icon_row.append(choose_icon)
        card.append(icon_row)
        card.append(Gtk.Label(label="Images are shown in the editor. Use 96 × 96 px for best results; larger PNG/JPEG files are resized by the official SDK.", xalign=0, wrap=True, css_classes=["muted"]))
        box.append(card)

        background = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9, css_classes=["inspector-card"])
        background.append(Gtk.Label(label="Device background", xalign=0, css_classes=["heading"]))
        self.background_entry = Gtk.Entry(placeholder_text="Optional JPG or PNG, exactly 854 × 480 recommended")
        background_row = Gtk.Box(spacing=8)
        background_row.append(self.background_entry)
        choose_background = Gtk.Button(label="Choose…")
        choose_background.connect("clicked", self._choose_background)
        background_row.append(choose_background)
        background.append(background_row)
        background.append(Gtk.Label(label="This is the real 854 × 480 touchscreen background supported by the 293S V3 SDK. It applies to the current page when the dock changes page.", xalign=0, wrap=True, css_classes=["muted"]))
        box.append(background)
        note = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, css_classes=["inspector-card"])
        note.append(Gtk.Label(label="Safe apply", xalign=0, css_classes=["heading"]))
        note.append(Gtk.Label(label="Applying writes the selected profile and restarts only this dock's user service. It never changes firmware.", xalign=0, wrap=True, css_classes=["muted"]))
        box.append(note)
        box.append(Gtk.Box(vexpand=True))
        scroll.set_child(box)
        return scroll

    def _footer(self) -> Gtk.Widget:
        bar = Gtk.ActionBar(margin_top=10, margin_bottom=12, margin_start=22, margin_end=22)
        self.status = Gtk.Label(label="Ready. Select a key to begin.", xalign=0)
        bar.pack_start(self.status)
        apply_button = Gtk.Button(label="Save and apply", css_classes=["suggested-action"])
        apply_button.connect("clicked", self._save_and_apply)
        bar.pack_end(apply_button)
        return bar

    def _page(self) -> dict:
        return self.profile["pages"][self.page_index]

    def _refresh_key_buttons(self) -> None:
        if not self.key_buttons:
            return
        page = self._page()
        self.page_indicator.set_label(f"{page['name']} · {self.page_index + 1}/{len(self.profile['pages'])}")
        self.remove_page.set_sensitive(len(self.profile["pages"]) > 1)
        for position, button in self.key_buttons.items():
            definition = page["keys"][position]
            number = POSITIONS.index(position) + 1
            label = definition.get("label", f"Key {number}").strip() or f"Key {number}"
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            icon = Path(definition.get("icon", "")).expanduser()
            if icon.is_file():
                image = Gtk.Image.new_from_file(str(icon))
                image.set_pixel_size(42)
                image.add_css_class("thumbnail")
                content.append(image)
            else:
                content.append(Gtk.Label(label=str(number), css_classes=["key-number"]))
            content.append(Gtk.Label(label=label, wrap=True, justify=Gtk.Justification.CENTER, css_classes=["key-name"]))
            button.set_child(content)
            button.remove_css_class("active")
            button.remove_css_class("navigation")
            if definition.get("role") in ("previous", "next"):
                button.add_css_class("navigation")
        self.key_buttons[self.selected].add_css_class("active")

    def _select_key(self, position: str) -> None:
        self.selected = position
        definition = self._page()["keys"][position]
        number = POSITIONS.index(position) + 1
        x, y = (int(value) for value in position.split("x", maxsplit=1))
        self.key_context.set_label(f"Physical key {number} · row {y + 1}, column {x + 1}")
        self.label_entry.set_text(definition.get("label", ""))
        self.command_entry.set_text(definition.get("command", ""))
        self.icon_entry.set_text(definition.get("icon", ""))
        self.background_entry.set_text(self._page().get("background_image", ""))
        if definition.get("role") in ("previous", "next"):
            self.command_entry.set_sensitive(False)
            self.command_help.set_label("This physical key changes dock pages. Its command is intentionally disabled.")
        else:
            self.command_entry.set_sensitive(True)
            self.command_help.set_label("Leave Command empty to display a key without an action.")
        self._refresh_key_buttons()

    def _change_page(self, direction: int) -> None:
        self._store_current_key()
        self.page_index = (self.page_index + direction) % len(self.profile["pages"])
        self._select_key(self.selected)

    def _add_page(self, _button: Gtk.Button) -> None:
        self._store_current_key()
        page = copy.deepcopy(self._page())
        page["name"] = f"Page {len(self.profile['pages']) + 1}"
        self.profile["pages"].append(page)
        self.page_index = len(self.profile["pages"]) - 1
        self._select_key(self.selected)

    def _remove_page(self, _button: Gtk.Button) -> None:
        if len(self.profile["pages"]) == 1:
            return
        self.profile["pages"].pop(self.page_index)
        self.page_index = min(self.page_index, len(self.profile["pages"]) - 1)
        self._select_key(self.selected)

    def _choose_icon(self, _button: Gtk.Button) -> None:
        self._choose_file("Choose key image", self._icon_chosen)

    def _choose_background(self, _button: Gtk.Button) -> None:
        self._choose_file("Choose 854 × 480 background", self._background_chosen)

    def _choose_file(self, title: str, response_handler) -> None:
        dialog = Gtk.FileChooserNative.new(title, self.props.active_window, Gtk.FileChooserAction.OPEN, "Choose", "Cancel")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images (PNG, JPEG)")
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/jpeg")
        dialog.add_filter(image_filter)
        dialog.connect("response", response_handler)
        dialog.show()

    def _icon_chosen(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            path = dialog.get_file().get_path()
            if path:
                self.icon_entry.set_text(path)
                self._page()["keys"][self.selected]["icon"] = path
                self._refresh_key_buttons()
        dialog.destroy()

    def _background_chosen(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            path = dialog.get_file().get_path()
            if path:
                self.background_entry.set_text(path)
        dialog.destroy()

    def _store_current_key(self) -> bool:
        definition = self._page()["keys"][self.selected]
        label = self.label_entry.get_text().strip()
        if not label:
            self.status.set_label("A key needs a label so it remains identifiable.")
            self.status.set_css_classes(["status-error"])
            self.label_entry.grab_focus()
            return False
        definition["label"] = label
        if definition.get("role") not in ("previous", "next"):
            definition["command"] = self.command_entry.get_text().strip()
        definition["icon"] = self.icon_entry.get_text().strip()
        self._page()["background_image"] = self.background_entry.get_text().strip()
        return True

    def _store_side_displays(self) -> None:
        for key, dropdown in self.side_modes.items():
            self.profile["side_displays"][key] = {"mode": SIDE_MODES[dropdown.get_selected()], "text": self.side_texts[key].get_text().strip()}

    def _open_profile(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative.new("Open Stream Dock profile", self.props.active_window, Gtk.FileChooserAction.OPEN, "Open", "Cancel")
        profile_filter = Gtk.FileFilter()
        profile_filter.set_name("Profile JSON")
        profile_filter.add_pattern("*.json")
        dialog.add_filter(profile_filter)
        dialog.connect("response", self._profile_opened)
        dialog.show()

    def _profile_opened(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            chosen = dialog.get_file().get_path()
            if chosen:
                try:
                    self.profile, self.profile_path = load_profile(Path(chosen))
                    select_profile(self.profile_path)
                    self.page_index = 0
                    self._load_side_widgets()
                    self._select_key("0x0")
                    self._refresh_profile_label()
                    self.status.set_label("Profile opened. Save and apply when you are ready.")
                    self.status.set_css_classes(["status-ok"])
                except (OSError, ValueError, KeyError) as error:
                    self.status.set_label(f"Could not open that profile: {error}")
                    self.status.set_css_classes(["status-error"])
        dialog.destroy()

    def _save_as(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative.new("Save Stream Dock profile as", self.props.active_window, Gtk.FileChooserAction.SAVE, "Save", "Cancel")
        dialog.set_current_name("stream-dock-profile.json")
        dialog.connect("response", self._profile_saved_as)
        dialog.show()

    def _profile_saved_as(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            chosen = dialog.get_file().get_path()
            if chosen:
                if not self._store_current_key():
                    dialog.destroy()
                    return
                self._store_side_displays()
                self.profile_path = Path(chosen if chosen.endswith(".json") else f"{chosen}.json")
                write_json(self.profile_path, self.profile)
                select_profile(self.profile_path)
                self._refresh_profile_label()
                self.status.set_label("Profile saved at the selected location.")
                self.status.set_css_classes(["status-ok"])
        dialog.destroy()

    def _refresh_profile_label(self) -> None:
        self.profile_label.set_label(str(self.profile_path))
        self.profile_label.set_tooltip_text(str(self.profile_path))

    def _save_and_apply(self, _button: Gtk.Button) -> None:
        if not self._store_current_key():
            return
        self._store_side_displays()
        write_json(self.profile_path, self.profile)
        select_profile(self.profile_path)
        result = subprocess.run(["systemctl", "--user", "restart", SERVICE], capture_output=True, text=True, check=False)
        self._refresh_key_buttons()
        if result.returncode == 0:
            self.status.set_label("Saved and applied to the Mirabox Stream Dock 293S V3.")
            self.status.set_css_classes(["status-ok"])
        else:
            self.status.set_label("Saved locally, but the service could not restart. Run the installer or check the service status.")
            self.status.set_css_classes(["status-error"])


if __name__ == "__main__":
    StreamDockEditor().run(None)
