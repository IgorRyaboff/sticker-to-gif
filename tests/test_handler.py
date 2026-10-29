import pytest

from sticker_bot import handler
from sticker_bot.handler import classify, handle, handle_update

FILE = {"file_id": "fid", "file_unique_id": "uid", "file_size": 1000}
MSG = {"message_id": 7, "chat": {"id": 42}}


@pytest.mark.parametrize(
    ("msg", "expected"),
    [
        ({"sticker": {**FILE, "is_animated": False, "is_video": False}}, ("webp", "png")),
        ({"sticker": {**FILE, "is_animated": True, "is_video": False}}, ("tgs", "gif")),
        ({"sticker": {**FILE, "is_animated": False, "is_video": True}}, ("webm", "gif")),
        ({"animation": {**FILE, "mime_type": "video/mp4"}, "document": {**FILE, "mime_type": "video/mp4"}}, ("mp4", "gif")),
        ({"animation": {**FILE, "mime_type": "image/gif"}}, ("gif", "gif")),
        ({"document": {**FILE, "mime_type": "image/gif"}}, ("gif", "gif")),
    ],
)
def test_classify(msg, expected):
    _, src_fmt, out_fmt = classify(msg)
    assert (src_fmt, out_fmt) == expected


@pytest.mark.parametrize(
    "msg",
    [{"text": "hi"}, {"photo": [FILE]}, {"video": FILE}, {"document": {**FILE, "mime_type": "application/pdf"}}],
)
def test_classify_unsupported(msg):
    assert classify(msg) is None


class FakeStore:
    def __init__(self, existing=None):
        self.existing = existing or {}
        self.puts = []

    def existing_url(self, key):
        return self.existing.get(key)

    def put(self, path, key):
        self.puts.append(key)
        return f"https://cdn.test/{key}"


@pytest.fixture
def calls(monkeypatch):
    calls = {"replies": [], "downloads": [], "tg": []}
    monkeypatch.setattr(handler, "reply", lambda msg, text: calls["replies"].append(text))
    monkeypatch.setattr(handler, "download", lambda file_id, dst: calls["downloads"].append(file_id))
    monkeypatch.setattr(handler, "tg", lambda method, **p: calls["tg"].append(method))
    return calls


def test_cache_hit_skips_download_and_replies_link_only(calls):
    store = FakeStore({"uid.png": "https://cdn.test/uid.png"})
    handle({**MSG, "sticker": {**FILE, "is_animated": False, "is_video": False}}, store)
    assert calls["replies"] == ["https://cdn.test/uid.png"]
    assert calls["downloads"] == [] and store.puts == []


def test_new_conversion_replies_with_link_and_stats(calls, monkeypatch):
    monkeypatch.setitem(handler.CONVERTERS, "webp", lambda src, dst: dst.write_bytes(b"x" * 2048) and None)
    store = FakeStore()
    handle({**MSG, "sticker": {**FILE, "is_animated": False, "is_video": False}}, store)
    assert store.puts == ["uid.png"]
    assert calls["tg"] == ["sendChatAction"]
    assert calls["replies"][0].startswith("https://cdn.test/uid.png\n\nwebp → png, 2 KB, converted in")
    assert "reduced" not in calls["replies"][0]


def test_reduction_note_is_appended_to_stats(calls, monkeypatch):
    def convert(src, dst):
        dst.write_bytes(b"x" * 1024)
        return "reduced to 20 fps, 384 px, 128 colors"

    monkeypatch.setitem(handler.CONVERTERS, "webm", convert)
    handle({**MSG, "sticker": {**FILE, "is_video": True}}, FakeStore())
    assert calls["replies"][0].endswith("s, reduced to 20 fps, 384 px, 128 colors")


def test_oversized_file_is_not_downloaded(calls):
    handle({**MSG, "animation": {**FILE, "file_size": 25 * 1024 * 1024, "mime_type": "video/mp4"}}, FakeStore())
    assert calls["downloads"] == []
    assert "20 MB" in calls["replies"][0]


def test_unsupported_message_gets_hint(calls):
    handle({**MSG, "text": "hello"}, FakeStore())
    assert calls["replies"] == ["Send me one sticker or GIF and I'll reply with a link."]


def test_handle_update_reports_failure_and_does_not_raise(calls, monkeypatch):
    def boom(src, dst):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setitem(handler.CONVERTERS, "webm", boom)
    handle_update({"message": {**MSG, "sticker": {**FILE, "is_video": True}}}, FakeStore())
    assert calls["replies"] == ["Sorry, conversion failed: ffmpeg failed"]


def test_handle_update_ignores_non_message_updates(calls):
    handle_update({"edited_message": MSG}, FakeStore())
    assert calls == {"replies": [], "downloads": [], "tg": []}
