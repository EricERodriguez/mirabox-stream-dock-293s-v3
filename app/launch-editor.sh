#!/usr/bin/env sh
set -eu

APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/mirabox-stream-dock-293s-v3"
cd "$APP_HOME/app"
exec "$APP_HOME/venv/bin/python" -m editor
