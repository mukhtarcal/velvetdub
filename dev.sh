#!/usr/bin/env bash
# Start the API (127.0.0.1:8765) and the web app (127.0.0.1:5273) together. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"

[ -d web/node_modules ] || npm --prefix web install

uv run vd serve &
api=$!
trap 'kill "$api" 2>/dev/null' EXIT INT TERM

npm --prefix web run dev
