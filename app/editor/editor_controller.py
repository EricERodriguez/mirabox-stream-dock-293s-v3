"""Editor logic and profile state, independent of GTK.

MainWindow (the view) reads and writes this object's state and calls its
methods; it never touches the profile dict directly. Nothing in this module
imports gi/Gtk, so the profile-editing rules here (adding/removing pages,
validating a key's label, applying and saving) can be reasoned about and
tested without a display.
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path

from profile_store import POSITIONS, load_profile, select_profile, write_json

SERVICE = "mirabox-stream-dock-293s-v3.service"
SIDE_MODES = ("clock", "cpu", "ram", "text")


class EditorState:
    def __init__(self) -> None:
        self.profile, self.profile_path = load_profile()
        self.page_index = 0
        self.selected = "0x0"

    def page(self) -> dict:
        return self.profile["pages"][self.page_index]

    def key_definition(self, position: str | None = None) -> dict:
        return self.page()["keys"][position or self.selected]

    def select(self, position: str) -> None:
        self.selected = position

    def change_page(self, direction: int) -> None:
        self.page_index = (self.page_index + direction) % len(self.profile["pages"])

    def add_page(self) -> None:
        page = copy.deepcopy(self.page())
        page["name"] = f"Page {len(self.profile['pages']) + 1}"
        self.profile["pages"].append(page)
        self.page_index = len(self.profile["pages"]) - 1

    def remove_page(self) -> bool:
        if len(self.profile["pages"]) == 1:
            return False
        self.profile["pages"].pop(self.page_index)
        self.page_index = min(self.page_index, len(self.profile["pages"]) - 1)
        return True

    def store_current_key(self, label: str, command: str, icon: str, background: str) -> bool:
        """Validate and persist the inspector's fields for the selected key.

        Returns False (and stores nothing) when the label is empty -- a key
        always needs a label so it stays identifiable in the grid.
        """
        label = label.strip()
        if not label:
            return False
        definition = self.key_definition()
        definition["label"] = label
        if definition.get("role") not in ("previous", "next"):
            definition["command"] = command.strip()
        definition["icon"] = icon.strip()
        self.page()["background_image"] = background.strip()
        return True

    def store_side_displays(self, values: dict[str, tuple[str, str]]) -> None:
        for key, (mode, text) in values.items():
            self.profile["side_displays"][key] = {"mode": mode, "text": text}

    def set_key_icon(self, path: str) -> None:
        self.key_definition()["icon"] = path

    def open_profile(self, path: Path) -> None:
        """May raise OSError/ValueError/KeyError for an unreadable or invalid file."""
        self.profile, self.profile_path = load_profile(path)
        select_profile(self.profile_path)
        self.page_index = 0
        self.selected = "0x0"

    def save_as(self, path: Path) -> None:
        self.profile_path = path if path.suffix == ".json" else path.with_suffix(".json")
        write_json(self.profile_path, self.profile)
        select_profile(self.profile_path)

    def save_and_apply(self) -> bool:
        write_json(self.profile_path, self.profile)
        select_profile(self.profile_path)
        result = subprocess.run(["systemctl", "--user", "restart", SERVICE], capture_output=True, text=True, check=False)
        return result.returncode == 0


__all__ = ["EditorState", "POSITIONS", "SIDE_MODES"]
