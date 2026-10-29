"""Vercel Function receiving Telegram webhook updates."""

import hmac
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sticker_bot.handler import handle_update  # noqa: E402
from sticker_bot.storage import require_r2_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("webhook")


def _authorized(header: str | None) -> bool:
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    return bool(secret) and hmac.compare_digest((header or "").encode(), secret.encode())


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if not _authorized(self.headers.get("X-Telegram-Bot-Api-Secret-Token")):
            self._respond(401)
            return
        try:
            update = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        except ValueError:
            log.warning("malformed update body")
            self._respond(400)
            return
        try:
            store = require_r2_store()
        except RuntimeError:
            # Telegram keeps the update and redelivers it once the deployment is fixed.
            log.exception("configuration error")
            self._respond(500)
            return
        handle_update(update, store)
        self._respond(200)

    def _respond(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()
