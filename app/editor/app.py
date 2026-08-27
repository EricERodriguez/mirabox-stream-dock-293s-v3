"""The GTK4 application entrypoint: creates the profile state and the
window, and presents it. Deliberately thin -- see editor_controller.py for
profile logic and main_window.py for the widget tree.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk

from .editor_controller import EditorState
from .main_window import MainWindow

APP_ID = "vip.key123.mirabox.StreamDock293SV3"


class StreamDockEditor(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        state = EditorState()
        window = MainWindow(application=self, state=state)
        window.present()
