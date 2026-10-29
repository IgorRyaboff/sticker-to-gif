## 1. Parameterized GIF encoding

- [x] 1.1 Add `_gif_filter(step, src, alpha, compact)` to `convert.py`, producing the fps (only when the source is faster), scale (only when the source is wider), palettegen (`max_colors`, `reserve_transparent` when alpha), and paletteuse stages; express today's alpha and MP4 filters as step 0 through it
- [x] 1.2 Read the source fps and width once per input: from rlottie for TGS, and from ffmpeg's input summary (`probe()`) for WebM and MP4
- [x] 1.3 Render TGS frames once and reuse the PNG sequence for every encode step

## 2. Budget loop

- [x] 2.1 Define the ladder (step 0 + the three steps from the spec, tightened against each source's own caps, consecutive duplicates skipped) and `gif_budget()` reading `GIF_MAX_BYTES` (default 5 MiB) at call time
- [x] 2.2 Implement the encode loop: encode a step into a temp file, stop at the first one under budget, otherwise keep the smallest; move the chosen file to `dst`
- [x] 2.3 Make the converters return `str | None` (the reduction note); static and passthrough return `None`
- [x] 2.4 Append the note to the stats line in `handler.handle`

## 3. Tests

- [x] 3.1 With a budget just under the full-quality size, the alpha WebM fixture output shrinks, keeps transparency and duration, and returns a note
- [x] 3.2 With the default budget, the existing fixtures produce no note and the same dimensions and fps as before
- [x] 3.3 With an unreachable budget (1 byte), the result is the smallest step and is still a valid GIF
- [x] 3.4 Caps never upscale: the 320×240 MP4 fixture keeps 320×240 at every step
- [x] 3.5 Handler test: the reply includes the note when the converter returns one, and none otherwise
- [x] 3.6 Add a photographic fixture (`testsrc2` + temporal noise at 512×512) that goes over the default budget at step 0 and fits at a later step

## 4. Ship

- [x] 4.1 Add a commented `GIF_MAX_BYTES` line to `.env` (unset = 5 MiB)
- [x] 4.2 Run the real 15 MB sticker (`~/Downloads/5ce23498-….webm`) through `webm_to_gif` locally; confirm it comes out under 5 MiB and looks right — 4.48 MiB at step 1 (20 fps, 384 px, 128 colors), 3,400 ms, 2.0 s
- [x] 4.3 Deploy to Vercel and check the runtime logs for conversion sizes — `dpl_CR6HXjDWJexuyDrYoiVqQTyNBzNY` READY in fra1; webhook answers 401 without secret
- [x] 4.4 With the user's go-ahead, delete `AgADCWYAAqujSEg.gif` from R2, resend the sticker, and confirm the new link is under budget — 4,669,197 bytes (4.45 MiB), 384×384, 68 frames, 3,400 ms, `image/gif`; 6.9 s on Vercel
