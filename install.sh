#!/usr/bin/env bash
# Install the Mirabox Stream Dock 293S V3 editor and official-SDK bridge.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_home="${XDG_DATA_HOME:-$HOME/.local/share}/mirabox-stream-dock-293s-v3"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}/mirabox-stream-dock-293s-v3"
sdk_tmp="$(mktemp -d)"
trap 'rm -rf "$sdk_tmp"' EXIT

command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 1; }
command -v git >/dev/null || { echo "git is required to fetch the official SDK." >&2; exit 1; }
if systemctl --user is-active --quiet streamdock-mirabox-293s-v3.service; then
  echo "Another Mirabox 293S V3 bridge is active (streamdock-mirabox-293s-v3.service)." >&2
  echo "Disable that older integration before installing this separate application." >&2
  exit 2
fi

install -d "$app_home/app/daemon" "$app_home/app/editor" "$app_home/assets" "$config_home" "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
install -m 0644 "$repo_root/profile.default.json" "$app_home/profile.default.json"
install -m 0644 "$repo_root/app/profile_store.py" "$app_home/app/"
install -m 0644 "$repo_root"/app/daemon/*.py "$app_home/app/daemon/"
install -m 0644 "$repo_root"/app/editor/*.py "$app_home/app/editor/"
install -m 0755 "$repo_root/app/launch-editor.sh" "$app_home/launch-editor.sh"
install -m 0644 "$repo_root/assets/mirabox-stream-dock-293s-v3.svg" "$app_home/assets/mirabox-stream-dock-293s-v3.svg"

if [[ ! -f "$config_home/profile.json" ]]; then
  install -m 0600 "$repo_root/profile.default.json" "$config_home/profile.json"
fi

git clone --depth 1 https://github.com/MiraboxSpace/StreamDock-Device-SDK.git "$sdk_tmp/sdk"
python3 -m venv --system-site-packages "$app_home/venv"
"$app_home/venv/bin/python" -m pip install --no-deps "$sdk_tmp/sdk/Python-SDK"

transport_dir="$("$app_home/venv/bin/python" - <<'PY'
import importlib.util
from pathlib import Path

spec = importlib.util.find_spec("StreamDock")
assert spec and spec.origin
print(Path(spec.origin).parent / "Transport")
PY
)"
cp -a "$sdk_tmp/sdk/Python-SDK/src/StreamDock/Transport/TransportDLL" "$transport_dir/"

sed "s|@APP_HOME@|$app_home|g" "$repo_root/app/mirabox-stream-dock-293s-v3.service" \
  > "$HOME/.config/systemd/user/mirabox-stream-dock-293s-v3.service"
sed "s|@APP_HOME@|$app_home|g" "$repo_root/app/mirabox-stream-dock-293s-v3.desktop" \
  > "$HOME/.local/share/applications/mirabox-stream-dock-293s-v3.desktop"

systemctl --user daemon-reload
systemctl --user enable --now mirabox-stream-dock-293s-v3.service

cat <<EOF

Installed. Open “Mirabox Stream Dock 293S V3” from the Applications menu.

To grant HID access, install the udev rule once:
  sudo install -m 0644 "$repo_root/app/70-mirabox-stream-dock-293s-v3.rules" /etc/udev/rules.d/70-mirabox-stream-dock-293s-v3.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger

Reconnect the dock if its current hidraw device retains old permissions.
EOF
