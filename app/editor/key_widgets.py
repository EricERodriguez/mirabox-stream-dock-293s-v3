"""Builds the visual content shown inside a deck-grid key button: a real
icon thumbnail when the key has one, otherwise its physical number and
label. Mirrors, in GTK terms, how the daemon's ``rendering.render_key()``
falls back to a generated tile when no icon file exists.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def build_key_content(definition: dict, number: int) -> Gtk.Widget:
    label = definition.get("label", f"Key {number}").strip() or f"Key {number}"
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
    icon = Path(definition.get("icon", "")).expanduser()
    if icon.is_file():
        image = Gtk.Image.new_from_file(str(icon))
        image.set_pixel_size(42)
        image.add_css_class("thumbnail")
        image.set_opacity(max(0, min(100, int(definition.get("opacity", 100)))) / 100)
        content.append(image)
    else:
        content.append(Gtk.Label(label=str(number), css_classes=["key-number"]))
    content.append(Gtk.Label(label=label, wrap=True, justify=Gtk.Justification.CENTER, css_classes=["key-name"]))
    return content
