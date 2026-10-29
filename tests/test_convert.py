import pytest
from PIL import Image, ImageSequence

from sticker_bot.convert import (
    DEFAULT_GIF_MAX_BYTES,
    gif_passthrough,
    mp4_to_gif,
    tgs_to_gif,
    webm_to_gif,
    webp_to_png,
)


def _frames(path):
    with Image.open(path) as im:
        return [(f.convert("RGBA"), f.info["duration"]) for f in ImageSequence.Iterator(im)]


def _assert_transparent_and_no_ghosting(path):
    frames = _frames(path)
    first, last = frames[0][0], frames[-1][0]
    x0, y0, x1, y1 = first.getbbox()
    center = ((x0 + x1) // 2, (y0 + y1) // 2)
    assert last.getpixel((2, 2))[3] == 0, "background must be transparent"
    assert last.getpixel(center)[3] == 0, "first frame's object must not remain in the last frame"
    return frames


@pytest.fixture(autouse=True)
def default_budget(monkeypatch):
    monkeypatch.delenv("GIF_MAX_BYTES", raising=False)


def test_webp_to_png_keeps_alpha(media, tmp_path):
    out = tmp_path / "out.png"
    webp_to_png(media / "in.webp", out)
    with Image.open(out) as im:
        assert im.format == "PNG" and im.size == (256, 256)
        assert im.convert("RGBA").getpixel((2, 2))[3] == 0


def test_tgs_to_gif(media, tmp_path):
    out = tmp_path / "out.gif"
    assert tgs_to_gif(media / "in.tgs", out) is None
    frames = _assert_transparent_and_no_ghosting(out)
    assert len(frames) == 50  # 60fps source capped at 50
    assert abs(sum(d for _, d in frames) - 1000) <= 50


def test_webm_to_gif(media, tmp_path):
    out = tmp_path / "out.gif"
    assert webm_to_gif(media / "in.webm", out) is None
    frames = _assert_transparent_and_no_ghosting(out)
    assert len(frames) == 60
    assert abs(sum(d for _, d in frames) - 2000) <= 100


def test_mp4_to_gif_caps_size_fps_and_length(media, tmp_path):
    out = tmp_path / "out.gif"
    assert mp4_to_gif(media / "in.mp4", out) is None
    with Image.open(out) as im:
        assert im.size == (480, 270)
    frames = _frames(out)
    total = sum(d for _, d in frames)
    assert abs(total - 30_000) <= 500
    assert len(frames) / (total / 1000) <= 15.5


def test_mp4_to_gif_does_not_upscale(media, tmp_path):
    out = tmp_path / "out.gif"
    mp4_to_gif(media / "small.mp4", out)
    with Image.open(out) as im:
        assert im.size == (320, 240)


def test_gif_passthrough_is_byte_identical(media, tmp_path):
    src = tmp_path / "src.gif"
    Image.new("P", (8, 8)).save(src)
    out = tmp_path / "out.gif"
    gif_passthrough(src, out)
    assert out.read_bytes() == src.read_bytes()


def test_over_budget_sticker_is_reduced_but_keeps_alpha_and_timing(media, tmp_path, monkeypatch):
    full = tmp_path / "full.gif"
    webm_to_gif(media / "in.webm", full)
    monkeypatch.setenv("GIF_MAX_BYTES", str(full.stat().st_size - 1))

    out = tmp_path / "out.gif"
    note = webm_to_gif(media / "in.webm", out)
    assert note == "reduced to 20 fps, 256 px, 128 colors"  # 256px source is below the 384px cap
    assert out.stat().st_size < full.stat().st_size
    frames = _assert_transparent_and_no_ghosting(out)
    assert abs(sum(d for _, d in frames) - 2000) <= 100


def test_unreachable_budget_keeps_smallest_valid_gif(media, tmp_path, monkeypatch):
    monkeypatch.setenv("GIF_MAX_BYTES", "1")
    out = tmp_path / "out.gif"
    note = webm_to_gif(media / "in.webm", out)
    assert note is not None
    with Image.open(out) as im:
        assert im.format == "GIF" and im.n_frames > 1


def test_caps_never_upscale_small_mp4(media, tmp_path, monkeypatch):
    monkeypatch.setenv("GIF_MAX_BYTES", "1")
    out = tmp_path / "out.gif"
    note = mp4_to_gif(media / "small.mp4", out)
    with Image.open(out) as im:
        assert im.size == (320, 240)
    assert note.startswith("reduced to ") and "320 px" in note


def test_photographic_sticker_fits_default_budget(media, tmp_path):
    out = tmp_path / "out.gif"
    note = webm_to_gif(media / "photo.webm", out)
    assert note is not None, "fixture should exceed the budget at full quality"
    assert out.stat().st_size <= DEFAULT_GIF_MAX_BYTES
    frames = _frames(out)
    assert abs(sum(d for _, d in frames) - 3000) <= 150
