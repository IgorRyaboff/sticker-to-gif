"""Minimal Telegram Bot API client."""

import os
from pathlib import Path

import requests

API_ROOT = "https://api.telegram.org"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # Bot API getFile limit


def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]


def tg(method: str, **params):
    data = requests.post(f"{API_ROOT}/bot{_token()}/{method}", json=params, timeout=70).json()
    if not data.get("ok"):
        raise RuntimeError(f"{method}: {data.get('description')}")
    return data["result"]


def reply(msg: dict, text: str) -> None:
    tg("sendMessage", chat_id=msg["chat"]["id"], text=text, reply_parameters={"message_id": msg["message_id"]})


def download(file_id: str, dst: Path) -> None:
    file_path = tg("getFile", file_id=file_id)["file_path"]
    with requests.get(f"{API_ROOT}/file/bot{_token()}/{file_path}", timeout=60) as r:
        r.raise_for_status()
        dst.write_bytes(r.content)
