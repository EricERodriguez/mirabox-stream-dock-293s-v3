#!/usr/bin/env sh
set -eu

APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/mirabox-stream-dock-293s-v3"
exec "$APP_HOME/venv/bin/python" "$APP_HOME/app/editor.py"
