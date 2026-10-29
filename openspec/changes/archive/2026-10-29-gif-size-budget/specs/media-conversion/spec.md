## ADDED Requirements

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
