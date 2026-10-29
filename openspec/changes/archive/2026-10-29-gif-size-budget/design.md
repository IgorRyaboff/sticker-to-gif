## Context

`convert.py` has three animated paths, all ending in a single ffmpeg palettegen/paletteuse pass:

| Source | Input to ffmpeg | Current encode |
|---|---|---|
| TGS | PNG frames rendered by rlottie at min(native, 50) fps | `ALPHA_GIF_FILTER`, native size, 256 colors |
| WebM | VP9 decoded with `libvpx-vp9` | `ALPHA_GIF_FILTER`, native fps and size, 256 colors |
| MP4 | H.264 | `OPAQUE_GIF_FILTER`: 15 fps, width ≤ 480, 256 colors, first 30 s |

Measured on the problem sticker (512×512, 30 fps, 102 frames, photographic, no alpha):

```
fps  width  colors   size
30   512    256     14.0 MB   ← today
20   384    128      4.7 MB
15   384     64      2.7 MB
```

Size scales roughly linearly with fps × pixels, and with palette size. Changing the dithering mode (Bayer + `diff_mode`) saved only 7%, because every frame really does differ.

## Goals / Non-Goals

**Goals:**
- Keep animated GIFs under a configurable byte budget whenever possible.
- Leave inputs that already fit completely unchanged: same bytes, same quality.
- Choose quality loss deterministically (a fixed ladder, not a search), so behavior is predictable and testable.

**Non-Goals:**
- Lossy LZW tricks (gifsicle `--lossy`) or external optimizers. They would add a binary to the Vercel bundle.
- Re-converting or migrating objects already in R2.
- Shortening animations. Duration is never reduced; only fps, size and colors change.
- A budget for PNG output or for passthrough GIFs.

## Decisions

### 1. Encode at full quality first, then step down a fixed ladder
The ladder is a list of caps. Each step applies `min(source value, cap)`, so a step never upscales and never raises fps:

```
step 0  (today's behavior; no extra caps)
step 1  fps ≤ 20   width ≤ 384   128 colors
step 2  fps ≤ 15   width ≤ 384    64 colors
step 3  fps ≤ 10   width ≤ 320    64 colors
```

The loop stops at the first result under budget. If none fit, it keeps the smallest. For the problem sticker, step 1 already fits (4.7 MB).
*Alternatives considered:*
- A binary search over quality: more encodes, and less predictable output.
- Estimating the right step from the step-0 size: fragile, because size isn't exactly linear.
- Always encoding at reduced settings: rejected, because it degrades the ~170 KB drawn stickers for no reason.

### 2. One shared filter builder for all three sources
`_gif_filter(fps_cap, width_cap, colors, alpha)` builds the filtergraph:
- `fps=…` is added only when the source frame rate is above the cap. ffmpeg's `fps` filter can't express "min(source, cap)", so the source frame rate is read once (`ffprobe`-free: from rlottie for TGS, and from ffmpeg's stream info for WebM/MP4).
- `scale='min(W,iw)':-2:flags=lanczos`, then `palettegen=max_colors=N` (with `reserve_transparent=1` in alpha mode) and the matching `paletteuse`.

MP4 step 0 keeps its current 15 fps / 480 px caps, so its first ladder step that changes anything is step 1 (384 px / 128 colors).
*Alternative considered:* per-source ladders. Rejected: one ladder is simpler, and the min() rule already adapts it to each source.

### 2a. Downgrade steps also switch to compact dithering
Step 0 keeps each source's current dithering, so stickers that fit encode byte-for-byte as before. Steps 1–3 use ordered (Bayer) dithering with `diff_mode=rectangle` for transparent stickers too. Without that, the real 15 MB sticker missed the budget at step 1 (5.3 MB) and dropped to step 2. With it, step 1 fits at 4.48 MiB.

### 3. Stay on the input timeline when lowering fps
Lowering fps with the `fps` filter drops frames but keeps timestamps, so total duration stays faithful. This preserves the existing "timing within 5%" requirement. TGS frames are rendered once into a temp directory, and every ladder step re-encodes from those same PNGs.

### 4. Converters report what they did
Animated converters return an optional note (`None` when step 0 fit, otherwise e.g. `"reduced to 20 fps, 384 px, 128 colors"`). `handler.handle` appends it to the stats line. Static and passthrough converters return `None`. This keeps the knowledge of the ladder inside `convert.py`.

### 5. The budget is an environment variable
`GIF_MAX_BYTES` (integer, bytes) defaults to `5 * 1024 * 1024`. It's read when a conversion runs, so tests can override it. It's a single global value; no per-user or per-type budgets.

## Risks / Trade-offs

- **Worst case adds three extra encodes.** → For a 3 s 512 px clip each step measured 0.3–0.5 s. For a 30 s MP4 the steps only get cheaper. This stays well within the 60 s limit.
- **Very long or complex MP4s can still exceed the budget at step 3.** → The smallest result is kept and delivered. The note in the reply makes the reduction visible, and the budget is a goal, not a hard limit.
- **64-color palettes can band smooth gradients.** → Only reached at steps 2–3, which only happen for content that's already huge. On the measured photographic sticker the difference wasn't visible at chat size.
- **Existing oversized objects stay cached.** → Document deleting the specific key (`AgADCWYAAqujSEg.gif`) so it regenerates under the new rules.

## Migration Plan

Deploy as usual. No data migration. Optionally delete the known 15 MB object from R2 so the next request regenerates it. `GIF_MAX_BYTES` doesn't need to be set unless a budget other than 5 MB is wanted.

## Open Questions

- Bitrix24's real limit for inline GIF previews isn't known. 5 MB is a conservative default, and `GIF_MAX_BYTES` lets it be tuned without a code change.
