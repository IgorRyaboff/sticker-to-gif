#!/usr/bin/env bash
# Set up the Python env and run the bot locally (long polling).
# Extra args go to scripts/poll.py, e.g. ./bootstrap.sh --take-over
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv

command -v ffmpeg >/dev/null || { echo "ffmpeg not found. Install it: brew install ffmpeg" >&2; exit 1; }
ffmpeg -hide_banner -decoders 2>/dev/null | grep libvpx-vp9 >/dev/null \
  || { echo "ffmpeg lacks the libvpx-vp9 decoder (needed for video sticker transparency)" >&2; exit 1; }

[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --disable-pip-version-check -r requirements-dev.txt

set -a; source .env; set +a
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] || { echo "Set TELEGRAM_BOT_TOKEN in .env" >&2; exit 1; }

exec "$VENV/bin/python" scripts/poll.py "$@"
