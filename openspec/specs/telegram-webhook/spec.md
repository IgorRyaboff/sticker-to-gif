# telegram-webhook Specification

## Purpose
TBD - created by archiving change sticker-to-gif-bot. Update Purpose after archive.
## Requirements
### Requirement: Webhook authentication
The webhook endpoint SHALL accept an update only when the `X-Telegram-Bot-Api-Secret-Token` header equals the configured `TELEGRAM_WEBHOOK_SECRET` (constant-time comparison). Otherwise it SHALL respond `401` without processing the update.

#### Scenario: Request from Telegram
- **WHEN** a POST arrives with the correct secret header
- **THEN** the update is processed and the endpoint responds `200`

#### Scenario: Forged request
- **WHEN** a POST arrives with a missing or wrong secret header
- **THEN** the endpoint responds `401`, and the bot sends no message

### Requirement: Updates are always acknowledged
For authenticated requests, the endpoint SHALL respond `200` after processing, even if conversion, storage, or a reply failed, so Telegram does not redeliver the update.

#### Scenario: Conversion fails
- **WHEN** an authenticated update triggers a conversion that raises an error
- **THEN** the user gets a reply saying the conversion failed, and the endpoint responds `200`

#### Scenario: Update without a message
- **WHEN** an authenticated update has no `message` field
- **THEN** the endpoint responds `200` and does nothing

### Requirement: Successful reply
After a successful conversion or cache hit, the bot SHALL reply to the user's message (as a reply to it) with the public link. For a new conversion, the reply SHALL also include the source and output formats, the output size, and the conversion time.

#### Scenario: New conversion
- **WHEN** a video sticker is converted for the first time
- **THEN** the bot replies to that message with the link and a line like `webm → gif, 42 KB, converted in 0.4s`

#### Scenario: Cached result
- **WHEN** the input was already converted before
- **THEN** the bot replies with the link only

### Requirement: Progress indication
For any input that needs conversion, the bot SHALL send a `sendChatAction` before downloading.

#### Scenario: Long conversion
- **WHEN** a Telegram GIF is being converted
- **THEN** the user sees the bot's "sending file" indicator until the reply arrives

### Requirement: Download size limit
If the source file's reported size exceeds 20 MB (the Bot API `getFile` limit), the bot SHALL reply that the file is too large and SHALL NOT try to download it.

#### Scenario: Oversized animation
- **WHEN** a Telegram GIF with `file_size` of 25 MB is received
- **THEN** the bot replies that the file is over the 20 MB limit

### Requirement: Retry safety
Processing the same update more than once SHALL NOT corrupt stored files or create different links for the same input.

#### Scenario: Telegram redelivers an update
- **WHEN** the same update is delivered twice
- **THEN** both runs produce the same link, and the stored object is valid

### Requirement: Local development mode
The same message handling SHALL be runnable locally via Bot API long polling, without a public URL, and SHALL fall back to local file storage when R2 is not configured. The webhook deployment SHALL require R2 to be configured.

#### Scenario: Local run without R2
- **WHEN** the local runner starts with only `TELEGRAM_BOT_TOKEN` set
- **THEN** it processes messages, saves outputs to a local folder, and replies with `file://` paths

#### Scenario: Webhook without R2
- **WHEN** the webhook function handles a request and an R2 variable is missing
- **THEN** it fails with a configuration error in the logs instead of writing to local storage

