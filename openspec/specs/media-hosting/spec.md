# media-hosting Specification

## Purpose
TBD - created by archiving change sticker-to-gif-bot. Update Purpose after archive.
## Requirements
### Requirement: Content-stable object keys
Each converted file SHALL be stored in the configured R2 bucket under the key `<file_unique_id>.<ext>`, where `file_unique_id` is Telegram's identifier for the source file and `<ext>` is `png` or `gif`.

#### Scenario: Key derived from the source file
- **WHEN** a sticker with `file_unique_id` `AgADxyz` is converted to GIF
- **THEN** the object is stored as `AgADxyz.gif`

### Requirement: Repeat inputs reuse the stored file
Before downloading or converting, the system SHALL check whether the object key already exists. If it exists, the system SHALL reply with its link and SHALL NOT download, convert, or upload anything.

#### Scenario: Same sticker sent twice
- **WHEN** a user sends a sticker that was converted earlier, by any user
- **THEN** the reply contains the same link as before, and no conversion runs

### Requirement: Permanent public links
The reply link SHALL be `<R2_PUBLIC_BASE_URL>/<key>`, be publicly readable without authentication, never expire, and end in `.png` or `.gif`. Presigned URLs SHALL NOT be used.

#### Scenario: Link opened by a third party
- **WHEN** someone with no credentials opens the link at any later time
- **THEN** the file is returned with HTTP 200

### Requirement: HTTP headers for embedding
Objects SHALL be uploaded with `Content-Type` `image/png` or `image/gif` to match the extension, and `Cache-Control: public, max-age=31536000, immutable`.

#### Scenario: Bitrix24 renders the link
- **WHEN** a GIF link is pasted into Bitrix24
- **THEN** the link responds with `Content-Type: image/gif`, and Bitrix24 shows it as an image

### Requirement: R2 jurisdiction support
The S3 endpoint SHALL be `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`, or `https://<R2_ACCOUNT_ID>.<R2_JURISDICTION>.r2.cloudflarestorage.com` when `R2_JURISDICTION` is set.

#### Scenario: EU bucket
- **WHEN** `R2_JURISDICTION=eu` is configured
- **THEN** requests to R2 go to `<account>.eu.r2.cloudflarestorage.com` and succeed

