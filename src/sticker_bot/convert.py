"""Converters from Telegram media formats to PNG / GIF.

Every converter takes (src, dst) paths, writes dst, and returns a short note
when the output was reduced to fit the GIF size budget (otherwise None).
"""

import functools
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from rlottie_python import LottieAnimation

# Browsers clamp GIF frame delays under 2cs, so >50fps plays slower, not smoother.
GIF_MAX_FPS = 50

# Telegram "GIFs" are arbitrary MP4 clips; keep the resulting GIF reasonably sized.
MP4_FPS = 15
MP4_MAX_WIDTH = 480
MP4_MAX_SECONDS = 30

DEFAULT_GIF_MAX_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class GifStep:
    """Encoding caps; None means keep the source value."""

    fps: float | None = None
    width: int | None = None
    colors: int = 256

    def tighten(self, other: "GifStep") -> "GifStep":
        def lower(a, b):
            return b if a is None else a if b is None else min(a, b)

        return GifStep(lower(self.fps, other.fps), lower(self.width, other.width), min(self.colors, other.colors))


@dataclass(frozen=True)
class Source:
    fps: float
    width: int


STICKER_GIF = GifStep()
MP4_GIF = GifStep(fps=MP4_FPS, width=MP4_MAX_WIDTH)

# Tried in order, on top of the source's own step, until the GIF fits the budget.
# Measured on a 3.4s photographic 512px video sticker: 14.0 MB -> 4.7 MB -> 2.7 MB.
DOWNGRADE_LADDER = (
    GifStep(fps=20, width=384, colors=128),
    GifStep(fps=15, width=384, colors=64),
    GifStep(fps=10, width=320, colors=64),
)


def gif_budget() -> int:
    return int(os.environ.get("GIF_MAX_BYTES") or DEFAULT_GIF_MAX_BYTES)


@functools.cache
def ffmpeg_exe() -> str:
    """System ffmpeg when present (local dev), else the static build shipped by imageio-ffmpeg (Vercel)."""
    if exe := shutil.which("ffmpeg"):
        return exe
    import imageio_ffmpeg

    exe = imageio_ffmpeg.get_ffmpeg_exe()
    if not os.access(exe, os.X_OK):
        # Deployment bundles may drop the exec bit, and the bundle dir is read-only.
        copy = Path(tempfile.gettempdir()) / "ffmpeg"
        if not os.access(copy, os.X_OK):
            shutil.copyfile(exe, copy)
            copy.chmod(0o755)
        exe = str(copy)
    return exe


def _ffmpeg(*args: str) -> None:
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-500:]}")


def probe(src: Path) -> Source:
    """Frame rate and width of the first video stream, from ffmpeg's input summary (no ffprobe on Vercel)."""
    stderr = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(src)], capture_output=True, text=True).stderr
    line = next((ln for ln in stderr.splitlines() if "Video:" in ln), "")
    size = re.search(r", (\d+)x(\d+)", line)
    rate = re.search(r"([\d.]+) fps", line) or re.search(r"([\d.]+) tbr", line)
    if not (size and rate):
        raise RuntimeError(f"can't read video stream info: {line or stderr.strip()[-300:]}")
    return Source(fps=float(rate.group(1)), width=int(size.group(1)))


COMPACT_DITHER = "dither=bayer:bayer_scale=4:diff_mode=rectangle"


def _gif_filter(step: GifStep, src: Source, alpha: bool, compact: bool = False) -> str:
    """`compact` trades the default error-diffusion dither for ordered dithering, which compresses better."""
    stages = []
    if step.fps and step.fps < src.fps:
        stages.append(f"fps={step.fps:g}")
    if step.width and step.width < src.width:
        stages.append(f"scale={step.width}:-1:flags=lanczos")
    if alpha:
        # One palette for the whole clip, with a slot reserved for transparency.
        # Pixels below alpha_threshold become fully transparent (GIF alpha is 1-bit).
        stages.append("format=rgba")
        palette = f"palettegen=max_colors={step.colors}:reserve_transparent=1"
        use = "paletteuse=alpha_threshold=128" + (f":{COMPACT_DITHER}" if compact else "")
    else:
        palette = f"palettegen=max_colors={step.colors}:stats_mode=diff"
        use = f"paletteuse={COMPACT_DITHER}"
    return ",".join([*stages, "split[a][b]"]) + f";[a]{palette}[p];[b][p]{use}"


def _describe(step: GifStep, src: Source) -> str:
    fps = min(step.fps or src.fps, src.fps)
    width = min(step.width or src.width, src.width)
    return f"reduced to {fps:g} fps, {width} px, {step.colors} colors"


def _encode_gif(dst: Path, inputs: list[str], src: Source, base: GifStep, alpha: bool) -> str | None:
    """Encode with `base`, then down the ladder until the GIF fits the budget; keep the smallest otherwise."""
    budget = gif_budget()
    steps = [base]
    for rung in DOWNGRADE_LADDER:
        if (step := base.tighten(rung)) != steps[-1]:
            steps.append(step)

    with tempfile.TemporaryDirectory() as tmp:
        smallest = None
        for i, step in enumerate(steps):
            out = Path(tmp) / f"{i}.gif"
            _ffmpeg(*inputs, "-filter_complex", _gif_filter(step, src, alpha, compact=i > 0), "-loop", "0", str(out))
            size = out.stat().st_size
            if smallest is None or size < smallest[0]:
                smallest = (size, out, i, step)
            if size <= budget:
                chosen = (out, i, step)
                break
        else:
            chosen = smallest[1:]
        out, i, step = chosen
        shutil.move(out, dst)
    return None if i == 0 else _describe(step, src)


def webp_to_png(src: Path, dst: Path) -> None:
    """Static sticker. PNG, not JPG: stickers rely on transparency."""
    with Image.open(src) as im:
        im.save(dst, "PNG", optimize=True)


def webm_to_gif(src: Path, dst: Path) -> str | None:
    """Video sticker (VP9 with alpha).

    `-c:v libvpx-vp9` before `-i` forces the libvpx decoder: ffmpeg's native
    VP9 decoder ignores the alpha channel and yields a black background.
    """
    return _encode_gif(dst, ["-c:v", "libvpx-vp9", "-i", str(src)], probe(src), STICKER_GIF, alpha=True)


def tgs_to_gif(src: Path, dst: Path) -> str | None:
    """Animated sticker (gzipped Lottie): render frames once with rlottie, encode with ffmpeg."""
    anim = LottieAnimation.from_tgs(str(src))
    fps = min(round(anim.lottie_animation_get_framerate()), GIF_MAX_FPS)
    frames = max(1, round(anim.lottie_animation_get_duration() * fps))
    width, _ = anim.lottie_animation_get_size()

    with tempfile.TemporaryDirectory() as tmp:
        for i in range(frames):
            frame_num = anim.lottie_animation_get_frame_at_pos(i / frames)
            anim.render_pillow_frame(frame_num=frame_num).save(Path(tmp) / f"{i:04d}.png")
        inputs = ["-framerate", str(fps), "-i", str(Path(tmp) / "%04d.png")]
        return _encode_gif(dst, inputs, Source(fps=fps, width=width), STICKER_GIF, alpha=True)


def mp4_to_gif(src: Path, dst: Path) -> str | None:
    """Telegram "GIF" (animation message): H.264 MP4 without audio."""
    return _encode_gif(dst, ["-t", str(MP4_MAX_SECONDS), "-i", str(src)], probe(src), MP4_GIF, alpha=False)


def gif_passthrough(src: Path, dst: Path) -> None:
    """A real .gif sent as a file: already what we want."""
    shutil.copyfile(src, dst)


CONVERTERS = {
    "webp": webp_to_png,
    "webm": webm_to_gif,
    "tgs": tgs_to_gif,
    "mp4": mp4_to_gif,
    "gif": gif_passthrough,
}
