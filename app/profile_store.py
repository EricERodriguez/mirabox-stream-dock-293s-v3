"""Profile schema, migration and user-selected profile location support."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path


APP_HOME = Path(__file__).resolve().parent.parent
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mirabox-stream-dock-293s-v3"
DEFAULT_PROFILE = APP_HOME / "profile.default.json"
SETTINGS = CONFIG_HOME / "settings.json"
DEFAULT_USER_PROFILE = CONFIG_HOME / "profile.json"
POSITIONS = tuple(f"{x}x{y}" for y in range(3) for x in range(5))
NAVIGATION = {"0x2": ("previous", "Previous"), "4x2": ("next", "Next")}


def _default_key(position: str) -> dict:
    number = POSITIONS.index(position) + 1
    key = {"label": f"Key {number}", "command": "", "icon": "", "opacity": 100}
    if position in NAVIGATION:
        role, label = NAVIGATION[position]
        key.update({"label": label, "role": role})
    return key


def normalise(profile: dict) -> dict:
    """Accept the initial one-page schema and the current multi-page schema."""
    profile = copy.deepcopy(profile)
    if not isinstance(profile.get("pages"), list):
        profile["pages"] = [{"name": "Page 1", "background_image": profile.pop("background_image", ""), "keys": profile.pop("keys", {})}]
    if not profile["pages"]:
        profile["pages"] = [{"name": "Page 1", "background_image": "", "keys": {}}]
    for index, page in enumerate(profile["pages"], start=1):
        page.setdefault("name", f"Page {index}")
        page.setdefault("background_image", "")
        keys = page.setdefault("keys", {})
        for position in POSITIONS:
            key = keys.setdefault(position, _default_key(position))
            if isinstance(key, dict) and "states" in key:
                state = key.get("states", {}).get("0", {})
                actions = state.get("actions", [])
                command = actions[0].get("settings", {}).get("command", "") if actions else ""
                key = {
                    "label": state.get("labels", {}).get("bottom", {}).get("text", _default_key(position)["label"]),
                    "command": command,
                    "icon": state.get("media", {}).get("path", ""),
                }
                keys[position] = key
            key.setdefault("label", _default_key(position)["label"])
            key.setdefault("command", "")
            key.setdefault("icon", "")
            key.setdefault("opacity", 100)
            if position in NAVIGATION:
                key.setdefault("role", NAVIGATION[position][0])
    displays = profile.setdefault("side_displays", {})
    for index, key in enumerate(("16", "17", "18")):
        displays.setdefault(key, {"mode": ("clock", "cpu", "ram")[index], "text": ""})
        displays[key].setdefault("mode", "text")
        displays[key].setdefault("text", "")
    profile.setdefault("shared_background", False)
    profile.setdefault("background_image", "")
    profile["version"] = 2
    return profile


def active_background(profile: dict, page: dict) -> str:
    """The background path that actually applies to ``page``: the profile-wide
    one when "same background on every page" is on, otherwise the page's own.
    """
    if profile.get("shared_background"):
        return str(profile.get("background_image", ""))
    return str(page.get("background_image", ""))


def default_profile() -> dict:
    return normalise(json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8")))


def load_settings() -> dict:
    if not SETTINGS.exists():
        return {}
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def active_profile_path() -> Path:
    selected = load_settings().get("profile_path")
    return Path(selected).expanduser() if selected else DEFAULT_USER_PROFILE


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_profile(path: Path | None = None) -> tuple[dict, Path]:
    path = (path or active_profile_path()).expanduser()
    if not path.exists():
        write_json(path, default_profile())
    return normalise(json.loads(path.read_text(encoding="utf-8"))), path


def select_profile(path: Path) -> None:
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)
    write_json(SETTINGS, {"profile_path": str(path.expanduser().resolve())})
