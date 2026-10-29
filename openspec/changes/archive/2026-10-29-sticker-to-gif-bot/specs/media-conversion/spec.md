## ADDED Requirements

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
