"""Message handling shared by the Vercel webhook and the local polling runner."""

import logging
import tempfile
import time
from pathlib import Path

from .convert import CONVERTERS
from .storage import LocalStore, R2Store
from .telegram import MAX_DOWNLOAD_BYTES, download, reply, tg

log = logging.getLogger(__name__)


def classify(msg: dict) -> tuple[dict, str, str] | None:
    """Return (file object, source format, output format) or None if unsupported."""
    if s := msg.get("sticker"):
        if s.get("is_animated"):
            return s, "tgs", "gif"
        if s.get("is_video"):
            return s, "webm", "gif"
        return s, "webp", "png"
    # `animation` messages also carry a `document` field, so check it first.
    if a := msg.get("animation"):
        return a, ("gif" if a.get("mime_type") == "image/gif" else "mp4"), "gif"
    if (d := msg.get("document")) and d.get("mime_type") == "image/gif":
        return d, "gif", "gif"
    return None


def handle(msg: dict, store: R2Store | LocalStore) -> None:
    kind = classify(msg)
    if kind is None:
        reply(msg, "Send me one sticker or GIF and I'll reply with a link.")
        return
    file, src_fmt, out_fmt = kind

    key = f"{file['file_unique_id']}.{out_fmt}"
    if url := store.existing_url(key):
        log.info("cache hit %s", key)
        reply(msg, url)
        return

    if file.get("file_size", 0) > MAX_DOWNLOAD_BYTES:
        reply(msg, "That file is over Telegram's 20 MB bot download limit.")
        return

    tg("sendChatAction", chat_id=msg["chat"]["id"], action="upload_document")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / f"in.{src_fmt}", Path(tmp) / key
        download(file["file_id"], src)
        started = time.monotonic()
        note = CONVERTERS[src_fmt](src, dst)
        elapsed = time.monotonic() - started
        size_kb = dst.stat().st_size / 1024
        url = store.put(dst, key)

    stats = f"{src_fmt} → {out_fmt}, {size_kb:.0f} KB, converted in {elapsed:.1f}s"
    if note:
        stats += f", {note}"
    log.info("%s -> %s (%s)", src_fmt, key, stats)
    reply(msg, f"{url}\n\n{stats}")


def handle_update(update: dict, store: R2Store | LocalStore) -> None:
    """Process one update; never raises, so the caller can always acknowledge it."""
    if not (msg := update.get("message")):
        return
    try:
        handle(msg, store)
    except Exception as e:
        log.exception("failed to handle message")
        try:
            reply(msg, f"Sorry, conversion failed: {e}")
        except Exception:
            log.exception("failed to send failure reply")
