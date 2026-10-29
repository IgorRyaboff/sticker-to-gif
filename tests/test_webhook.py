import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from conftest import ROOT

SECRET = "s3cret"


@pytest.fixture
def webhook(monkeypatch):
    spec = importlib.util.spec_from_file_location("webhook", ROOT / "api" / "webhook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    handled = []
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(module, "require_r2_store", lambda: "store")
    monkeypatch.setattr(module, "handle_update", lambda update, store: handled.append(update))

    server = HTTPServer(("127.0.0.1", 0), module.handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/webhook", handled, module
    server.shutdown()


def _post(url, body, secret=None):
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.parametrize("secret", [None, "wrong"])
def test_rejects_missing_or_wrong_secret(webhook, secret):
    url, handled, _ = webhook
    assert _post(url, {"update_id": 1, "message": {}}, secret) == 401
    assert handled == []


def test_accepts_valid_update(webhook):
    url, handled, _ = webhook
    update = {"update_id": 1, "message": {"message_id": 1}}
    assert _post(url, update, SECRET) == 200
    assert handled == [update]


def test_non_message_update_is_acknowledged(webhook):
    url, handled, _ = webhook
    assert _post(url, {"update_id": 2, "edited_message": {}}, SECRET) == 200


def test_rejects_everything_when_secret_unset(webhook, monkeypatch):
    url, handled, _ = webhook
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "")
    assert _post(url, {"update_id": 1}, "") == 401
    assert handled == []


def test_missing_r2_config_fails_loudly(webhook, monkeypatch):
    url, handled, module = webhook
    from sticker_bot.storage import require_r2_store

    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(module, "require_r2_store", require_r2_store)
    assert _post(url, {"update_id": 3, "message": {}}, SECRET) == 500
    assert handled == []
