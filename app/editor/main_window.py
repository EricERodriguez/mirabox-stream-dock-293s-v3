"""The editor's window: builds every widget and wires its signals to the
EditorState it holds. This module is the "view" -- it reads and writes
GTK widgets, but the actual profile rules (validation, paging, saving)
live in editor_controller.EditorState.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from profile_store import POSITIONS

from .editor_controller import SIDE_MODES, EditorState
from .key_widgets import build_key_content
from .styles import CSS


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application, state: EditorState) -> None:
        super().__init__(application=application, title="Mirabox Stream Dock 293S V3")
        self.state = state
        self.key_buttons: dict[str, Gtk.Button] = {}
        self.side_modes: dict[str, Gtk.DropDown] = {}
        self.side_texts: dict[str, Gtk.Entry] = {}
        self._active_dialog: Gtk.FileChooserNative | None = None

        self._install_css()
        self.set_default_size(1220, 790)
        self.set_size_request(900, 620)
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
        self.set_child(root)
        self._select_key(self.state.selected)

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
        current = self.state.profile["side_displays"][key].get("mode", SIDE_MODES[number - 1])
        mode.set_selected(SIDE_MODES.index(current) if current in SIDE_MODES else 0)
        mode.connect("notify::selected", self._side_mode_changed, key)
        self.side_modes[key] = mode
        card.append(mode)
        text = Gtk.Entry(placeholder_text="Custom text")
        text.set_text(self.state.profile["side_displays"][key].get("text", ""))
        text.set_sensitive(current == "text")
        self.side_texts[key] = text
        card.append(text)
        return card

    def _side_mode_changed(self, dropdown: Gtk.DropDown, _value: object, key: str) -> None:
        self.side_texts[key].set_sensitive(SIDE_MODES[dropdown.get_selected()] == "text")

    def _load_side_widgets(self) -> None:
        for key, dropdown in self.side_modes.items():
            spec = self.state.profile["side_displays"][key]
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
        opacity_row = Gtk.Box(spacing=8)
        opacity_row.append(Gtk.Label(label="Icon opacity", xalign=0, css_classes=["heading"]))
        opacity_row.append(Gtk.Box(hexpand=True))
        self.opacity_value_label = Gtk.Label(label="100%", css_classes=["muted"])
        opacity_row.append(self.opacity_value_label)
        card.append(opacity_row)
        self.opacity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=Gtk.Adjustment(value=100, lower=0, upper=100, step_increment=1))
        self.opacity_scale.set_digits(0)
        self.opacity_scale.set_draw_value(False)
        self.opacity_scale.connect("value-changed", self._opacity_changed)
        card.append(self.opacity_scale)
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
        self.shared_background_check = Gtk.CheckButton(label="Use this background on every page")
        self.shared_background_check.set_active(self.state.is_shared_background())
        self.shared_background_check.connect("toggled", self._shared_background_toggled)
        background.append(self.shared_background_check)
        background.append(Gtk.Label(label="This is the real 854 × 480 touchscreen background supported by the 293S V3 SDK. It applies to the current page when the dock changes page, unless shared across every page above.", xalign=0, wrap=True, css_classes=["muted"]))
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

    def _refresh_key_buttons(self) -> None:
        if not self.key_buttons:
            return
        page = self.state.page()
        self.page_indicator.set_label(f"{page['name']} · {self.state.page_index + 1}/{len(self.state.profile['pages'])}")
        self.remove_page.set_sensitive(len(self.state.profile["pages"]) > 1)
        for position, button in self.key_buttons.items():
            definition = page["keys"][position]
            number = POSITIONS.index(position) + 1
            button.set_child(build_key_content(definition, number))
            button.remove_css_class("active")
            button.remove_css_class("navigation")
            if definition.get("role") in ("previous", "next"):
                button.add_css_class("navigation")
        self.key_buttons[self.state.selected].add_css_class("active")

    def _select_key(self, position: str) -> None:
        self.state.select(position)
        definition = self.state.key_definition()
        number = POSITIONS.index(position) + 1
        x, y = (int(value) for value in position.split("x", maxsplit=1))
        self.key_context.set_label(f"Physical key {number} · row {y + 1}, column {x + 1}")
        self.label_entry.set_text(definition.get("label", ""))
        self.command_entry.set_text(definition.get("command", ""))
        self.icon_entry.set_text(definition.get("icon", ""))
        self.opacity_scale.set_value(int(definition.get("opacity", 100)))
        self.opacity_value_label.set_label(f"{int(definition.get('opacity', 100))}%")
        self.background_entry.set_text(self.state.background_text())
        self.shared_background_check.set_active(self.state.is_shared_background())
        if definition.get("role") in ("previous", "next"):
            self.command_entry.set_sensitive(False)
            self.command_help.set_label("This physical key changes dock pages. Its command is intentionally disabled.")
        else:
            self.command_entry.set_sensitive(True)
            self.command_help.set_label("Leave Command empty to display a key without an action.")
        self._refresh_key_buttons()

    def _opacity_changed(self, scale: Gtk.Scale) -> None:
        value = int(scale.get_value())
        self.opacity_value_label.set_label(f"{value}%")
        self.state.set_key_opacity(value)
        self._refresh_key_buttons()

    def _store_current_key(self) -> bool:
        ok = self.state.store_current_key(
            self.label_entry.get_text(),
            self.command_entry.get_text(),
            self.icon_entry.get_text(),
            int(self.opacity_scale.get_value()),
            self.background_entry.get_text(),
            self.shared_background_check.get_active(),
        )
        if not ok:
            self.status.set_label("A key needs a label so it remains identifiable.")
            self.status.set_css_classes(["status-error"])
            self.label_entry.grab_focus()
        return ok

    def _shared_background_toggled(self, checkbox: Gtk.CheckButton) -> None:
        # Persist whatever background path is currently typed into whichever
        # mode was active *before* this toggle, so switching modes never
        # silently discards an unsaved edit.
        current_text = self.background_entry.get_text().strip()
        if self.state.is_shared_background():
            self.state.profile["background_image"] = current_text
        else:
            self.state.page()["background_image"] = current_text
        self.state.profile["shared_background"] = checkbox.get_active()
        self.background_entry.set_text(self.state.background_text())

    def _store_side_displays(self) -> None:
        self.state.store_side_displays({
            key: (SIDE_MODES[dropdown.get_selected()], self.side_texts[key].get_text().strip())
            for key, dropdown in self.side_modes.items()
        })

    def _change_page(self, direction: int) -> None:
        self._store_current_key()
        self.state.change_page(direction)
        self._select_key(self.state.selected)

    def _add_page(self, _button: Gtk.Button) -> None:
        self._store_current_key()
        self.state.add_page()
        self._select_key(self.state.selected)

    def _remove_page(self, _button: Gtk.Button) -> None:
        if self.state.remove_page():
            self._select_key(self.state.selected)

    def _choose_icon(self, _button: Gtk.Button) -> None:
        self._choose_file("Choose key image", self._icon_chosen)

    def _choose_background(self, _button: Gtk.Button) -> None:
        self._choose_file("Choose 854 × 480 background", self._background_chosen)

    def _choose_file(self, title: str, response_handler) -> None:
        # Gtk.FileChooserNative must stay referenced for as long as it is open:
        # PyGObject does not otherwise keep the wrapper alive once this method
        # returns, and the GC collecting it mid-dialog is what made these
        # buttons appear to do nothing (or crash) -- see self._active_dialog.
        dialog = Gtk.FileChooserNative.new(title, self, Gtk.FileChooserAction.OPEN, "Choose", "Cancel")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images (PNG, JPEG)")
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/jpeg")
        dialog.add_filter(image_filter)
        dialog.connect("response", response_handler)
        self._active_dialog = dialog
        dialog.show()

    def _icon_chosen(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            path = dialog.get_file().get_path()
            if path:
                self.icon_entry.set_text(path)
                self.state.set_key_icon(path)
                self._refresh_key_buttons()
        self._active_dialog = None
        dialog.destroy()

    def _background_chosen(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            path = dialog.get_file().get_path()
            if path:
                self.background_entry.set_text(path)
        self._active_dialog = None
        dialog.destroy()

    def _open_profile(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative.new("Open Stream Dock profile", self, Gtk.FileChooserAction.OPEN, "Open", "Cancel")
        profile_filter = Gtk.FileFilter()
        profile_filter.set_name("Profile JSON")
        profile_filter.add_pattern("*.json")
        dialog.add_filter(profile_filter)
        dialog.connect("response", self._profile_opened)
        self._active_dialog = dialog
        dialog.show()

    def _profile_opened(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            chosen = dialog.get_file().get_path()
            if chosen:
                try:
                    self.state.open_profile(Path(chosen))
                    self._load_side_widgets()
                    self._select_key("0x0")
                    self._refresh_profile_label()
                    self.status.set_label("Profile opened. Save and apply when you are ready.")
                    self.status.set_css_classes(["status-ok"])
                except (OSError, ValueError, KeyError) as error:
                    self.status.set_label(f"Could not open that profile: {error}")
                    self.status.set_css_classes(["status-error"])
        self._active_dialog = None
        dialog.destroy()

    def _save_as(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative.new("Save Stream Dock profile as", self, Gtk.FileChooserAction.SAVE, "Save", "Cancel")
        dialog.set_current_name("stream-dock-profile.json")
        dialog.connect("response", self._profile_saved_as)
        self._active_dialog = dialog
        dialog.show()

    def _profile_saved_as(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT and dialog.get_file():
            chosen = dialog.get_file().get_path()
            if chosen:
                if not self._store_current_key():
                    self._active_dialog = None
                    dialog.destroy()
                    return
                self._store_side_displays()
                self.state.save_as(Path(chosen))
                self._refresh_profile_label()
                self.status.set_label("Profile saved at the selected location.")
                self.status.set_css_classes(["status-ok"])
        self._active_dialog = None
        dialog.destroy()

    def _refresh_profile_label(self) -> None:
        self.profile_label.set_label(str(self.state.profile_path))
        self.profile_label.set_tooltip_text(str(self.state.profile_path))

    def _save_and_apply(self, _button: Gtk.Button) -> None:
        if not self._store_current_key():
            return
        self._store_side_displays()
        applied = self.state.save_and_apply()
        self._refresh_key_buttons()
        if applied:
            self.status.set_label("Saved and applied to the Mirabox Stream Dock 293S V3.")
            self.status.set_css_classes(["status-ok"])
        else:
            self.status.set_label("Saved locally, but the service could not restart. Run the installer or check the service status.")
            self.status.set_css_classes(["status-error"])
