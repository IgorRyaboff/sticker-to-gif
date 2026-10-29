import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sticker_bot.convert import ffmpeg_exe  # noqa: E402

# 1s, 60fps Lottie: a green square moving left to right on a transparent canvas.
LOTTIE = {
    "v": "5.5.2", "fr": 60, "ip": 0, "op": 60, "w": 512, "h": 512,
    "layers": [{
        "ty": 4, "ind": 1, "ip": 0, "op": 60, "st": 0,
        "ks": {
            "o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0},
            "p": {"a": 1, "k": [
                {"t": 0, "s": [60, 256, 0], "i": {"x": [1], "y": [1]}, "o": {"x": [0], "y": [0]}},
                {"t": 60, "s": [450, 256, 0]},
            ]},
            "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]},
        },
        "shapes": [
            {"ty": "rc", "p": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}},
            {"ty": "fl", "c": {"a": 0, "k": [0, 0.8, 0, 1]}, "o": {"a": 0, "k": 100}},
        ],
    }],
}


def _ffmpeg(*args: str) -> None:
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def media(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("media")

    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([50, 50, 130, 130], fill="blue")
    im.save(d / "in.webp")

    (d / "in.tgs").write_bytes(gzip.compress(json.dumps(LOTTIE).encode()))

    # 2s, 30fps VP9 with alpha: a red square moving right. drawbox doesn't touch
    # the alpha plane, so overlay an opaque square onto a transparent canvas.
    _ffmpeg(
        "-f", "lavfi", "-i", "color=c=black@0.0:s=256x256:r=30:d=2,format=rgba",
        "-f", "lavfi", "-i", "color=c=red:s=50x50:r=30,format=rgba",
        "-filter_complex", "[0][1]overlay=x='t*100':y=100:shortest=1,format=yuva420p",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", str(d / "in.webm"),
    )
    # Camera-like footage: every frame differs everywhere, so the GIF blows past the budget.
    _ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=s=512x512:r=30:d=3,noise=alls=40:allf=t",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-b:v", "4M", str(d / "photo.webm"),
    )
    _ffmpeg("-f", "lavfi", "-i", "testsrc=s=640x360:r=30:d=45", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "in.mp4"))
    _ffmpeg("-f", "lavfi", "-i", "testsrc=s=320x240:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "small.mp4"))
    return d
