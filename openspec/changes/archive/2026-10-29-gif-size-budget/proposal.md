## Why

A 3.4-second video sticker made from camera footage (a cat, with fur and camera shake) became a **15 MB GIF**. GIF has no inter-frame compression to speak of, so photographic content costs about 140 KB per 512×512 frame no matter how it's dithered. Files that large load slowly and risk being rejected or not previewed by Bitrix24. Measurements on that sticker show that lowering fps, size and palette brings it to 4.7 MB or 2.7 MB with no visible difference at chat size. Typical drawn stickers (about 170 KB) never get anywhere near that size.

## What Changes

- Animated GIF output (animated stickers, video stickers, Telegram GIFs) gets a **size budget**: 5 MB by default, configurable with `GIF_MAX_BYTES`.
- Conversion first encodes at full quality, exactly as today. Only if the result is over budget does it re-encode with a fixed **downgrade ladder** of progressively lower frame rate, width and palette size, stopping at the first step that fits.
- If even the last step exceeds the budget, the smallest result is kept, so the user still gets a link rather than an error.
- When output was downgraded, the bot's stats line says so, for example `reduced to 20 fps, 384 px, 128 colors`.
- Not affected: static stickers (PNG), real GIF files (passed through unchanged), and objects already stored in R2. Their keys are content-stable, so the existing 15 MB file stays cached until it's deleted manually.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `media-conversion`: adds the size-budget requirement for animated GIF output. The base spec comes from change `sticker-to-gif-bot`, which isn't archived yet, so this change's spec delta uses ADDED requirements and must be archived after it.

## Impact

- **Code**: `src/sticker_bot/convert.py` (parameterized GIF encoding, budget loop) and `handler.py` (include the downgrade note in the reply). Tests in `tests/test_convert.py`.
- **Config**: new optional env var `GIF_MAX_BYTES`, on Vercel and in `.env`.
- **Runtime**: only over-budget inputs pay for extra encodes, which measured 0.3–0.5 s per step for a 3.4 s 512 px clip. TGS frames are rendered once and reused across steps. This stays well within the 60 s `maxDuration`.
- **Dependencies**: none new.
