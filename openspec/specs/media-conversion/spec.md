# media-conversion Specification

## Purpose
TBD - created by archiving change sticker-to-gif-bot. Update Purpose after archive.
## Requirements
### Requirement: Supported inputs
The system SHALL accept exactly one media item per Telegram message and choose the conversion from the message content:

| Input | Detected by | Output |
|---|---|---|
| Static sticker | `sticker` with `is_animated=false` and `is_video=false` | PNG |
| Animated sticker | `sticker.is_animated=true` (TGS) | GIF |
| Video sticker | `sticker.is_video=true` (WebM) | GIF |
| Telegram "GIF" | `animation` with MP4 MIME type | GIF |
| GIF file | `animation` or `document` with `image/gif` MIME type | GIF (unchanged) |

The `animation` field SHALL be checked before `document`, because Telegram sets both on animation messages.

#### Scenario: Static sticker becomes PNG
- **WHEN** the user sends a static sticker
- **THEN** the system produces a PNG with the same dimensions as the sticker

#### Scenario: Animated sticker becomes GIF
- **WHEN** the user sends an animated (TGS) sticker
- **THEN** the system produces a looping GIF of the full animation

#### Scenario: Video sticker becomes GIF
- **WHEN** the user sends a video (WebM) sticker
- **THEN** the system produces a looping GIF of the full clip

#### Scenario: Telegram GIF becomes GIF
- **WHEN** the user sends a Telegram GIF (MP4 animation)
- **THEN** the system produces a looping GIF

#### Scenario: Real GIF file is passed through
- **WHEN** the user sends a file with MIME type `image/gif`
- **THEN** the system stores the file without re-encoding it

#### Scenario: Unsupported content
- **WHEN** the user sends text, a photo, a video, or any other message type
- **THEN** the system converts nothing and replies with a short hint that it accepts one sticker or GIF

### Requirement: Transparency is preserved
Converting a sticker SHALL preserve its transparency: PNG output SHALL keep the full alpha channel, and GIF output SHALL map pixels with alpha below 128 to the GIF transparent color. Video stickers SHALL be decoded with a decoder that reads VP9 alpha.

#### Scenario: Transparent background on a static sticker
- **WHEN** a static sticker with a transparent background is converted
- **THEN** the PNG's background pixels are fully transparent

#### Scenario: Transparent background on a video sticker
- **WHEN** a video sticker with a transparent background is converted
- **THEN** the GIF's background pixels are transparent in every frame, not black

### Requirement: Animated output does not ghost
Transparent animated GIF output SHALL clear each frame's transparent areas, so earlier frames don't remain visible behind later ones.

#### Scenario: Moving object on a transparent background
- **WHEN** an animated or video sticker shows an object moving across a transparent background
- **THEN** in the last GIF frame, the pixels where the object was in the first frame are transparent

### Requirement: Timing is faithful
Animated GIF output SHALL play at a total duration within 5% of the source animation. Frame rate SHALL be capped at 50 fps.

#### Scenario: 60 fps animated sticker
- **WHEN** a 1-second, 60 fps TGS sticker is converted
- **THEN** the GIF has 50 frames and a total duration of 1000 ms ± 50 ms

#### Scenario: 30 fps video sticker
- **WHEN** a 2-second, 30 fps video sticker is converted
- **THEN** the GIF's total duration is 2000 ms ± 100 ms

### Requirement: Telegram GIF size limits
Converting a Telegram GIF (MP4) to GIF SHALL output at most 15 fps, scale the width down to at most 480 px while keeping the aspect ratio (never upscaling), and include at most the first 30 seconds.

#### Scenario: Wide, long clip
- **WHEN** a 640×360, 45-second MP4 animation is converted
- **THEN** the GIF is 480×270, at most 15 fps, and about 30 seconds long

#### Scenario: Small clip
- **WHEN** a 320×240 MP4 animation is converted
- **THEN** the GIF stays 320×240

### Requirement: Animated GIF size budget
Animated GIF output (from animated stickers, video stickers, and Telegram GIFs) SHALL be kept within a byte budget, `GIF_MAX_BYTES`, which defaults to 5 MiB (5,242,880 bytes). The system SHALL first encode with the standard settings. If the result exceeds the budget, it SHALL re-encode with these steps in order, applying each cap only when it is lower than the source value:

| Step | Max fps | Max width | Palette colors |
|---|---|---|---|
| 1 | 20 | 384 px | 128 |
| 2 | 15 | 384 px | 64 |
| 3 | 10 | 320 px | 64 |

The system SHALL output the first result that fits the budget. If no step fits, it SHALL output the smallest result produced. Total duration SHALL stay within 5% of the source at every step. Static PNG output and passed-through GIF files SHALL NOT be affected.

#### Scenario: Output under budget is unchanged
- **WHEN** a video sticker converts to a 170 KB GIF with the standard settings
- **THEN** that GIF is output, and no downgraded encode is attempted

#### Scenario: Oversized output is downgraded until it fits
- **WHEN** a 512×512, 30 fps, 3.4 s photographic video sticker produces a 14 MB GIF with the standard settings
- **THEN** the output is the step-1 encode (at most 20 fps, 384×384, at most 128 colors), is under 5 MiB, and lasts 3.4 s ± 5%

#### Scenario: Nothing fits
- **WHEN** every step's result exceeds the budget
- **THEN** the smallest result is output, and the user still gets a link

#### Scenario: Caps never upscale
- **WHEN** a 320×240, 15 fps Telegram GIF exceeds the budget
- **THEN** downgraded steps keep 320×240 and 15 fps until a step's cap is below the source value, and only the palette shrinks before that

#### Scenario: Budget is configurable
- **WHEN** `GIF_MAX_BYTES` is set to 1048576
- **THEN** output over 1 MiB triggers the downgrade steps

### Requirement: Downgrade is reported to the user
When animated output was downgraded to meet the budget, the reply's stats line SHALL state the settings that were used.

#### Scenario: Downgraded sticker reply
- **WHEN** a sticker's GIF is produced by step 1
- **THEN** the reply contains `reduced to 20 fps, 384 px, 128 colors` (with each value shown as the one actually applied)

#### Scenario: Normal sticker reply
- **WHEN** the standard encode fits the budget
- **THEN** the reply contains no reduction note

