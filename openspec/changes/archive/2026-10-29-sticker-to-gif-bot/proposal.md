## Why

Bitrix24 only renders GIFs from links, and Telegram stickers and "GIFs" (actually WebP, TGS/Lottie, VP9 WebM, or H.264 MP4) can't be pasted there. A local proof of concept (`src/poc`) showed that every Telegram format can be converted and hosted on R2 with a permanent link. This change turns that POC into an always-on bot hosted on Vercel, so that friends can use it without someone's laptop running.

## What Changes

- New Telegram bot that accepts **one media item per message** and replies with a permanent public link:
  - static sticker (`.webp`) → PNG with transparency
  - animated sticker (`.tgs`, Lottie) → GIF (rendered with rlottie)
  - video sticker (`.webm`, VP9 + alpha) → GIF with 1-bit transparency
  - Telegram "GIF" (`.mp4` animation) → GIF capped at 15 fps, 480 px wide, 30 s
  - a real `.gif` sent as a file → uploaded unchanged
- Converted files are stored in a public Cloudflare R2 bucket (EU jurisdiction) and served from its `r2.dev` URL. The object key is Telegram's `file_unique_id`, so the same input always gets the same link and is converted only once.
- The bot runs as a Vercel Python Function that receives Telegram webhooks, verified with Telegram's secret-token header.
- The POC conversion and storage logic becomes a shared package used by both the Vercel webhook and a local long-polling runner for development.
- The bot is public: no allowlist and no rate limiting (intended audience is a small group of friends).

## Capabilities

### New Capabilities
- `media-conversion`: Which Telegram inputs are accepted and what each one is converted to, including transparency, frame-rate, and size limits.
- `media-hosting`: Storing converted files in R2 under content-stable keys, cache-hit behavior, public URL format, and HTTP headers (content type, immutable caching) that Bitrix24 relies on.
- `telegram-webhook`: Receiving updates on Vercel, authenticating them, replying to the user (link, unsupported input, size limit, failures), and staying correct when Telegram retries.

### Modified Capabilities
<!-- none: no existing specs -->

## Impact

- **New code**: a shared Python package (conversion, storage, Telegram client, message handling), a Vercel function entrypoint, `vercel.json`, a root `requirements.txt`, and a webhook registration script.
- **POC**: `src/poc` is replaced by the shared package. A local polling runner keeps the `bootstrap.sh` workflow.
- **Dependencies**: `rlottie-python`, `Pillow`, `boto3`, `requests`, plus a static Linux ffmpeg build with the `libvpx-vp9` decoder, bundled into the function (Vercel Python bundle limit: 500 MB).
- **External systems**: Telegram Bot API (webhook mode, so the bot can no longer use local polling at the same time); Cloudflare R2 bucket `tg-stickers-to-bot` with its public `r2.dev` URL enabled; a Vercel project with environment variables for the bot token, webhook secret, and R2 credentials.
- **Known limits**: Cloudflare rate-limits `r2.dev` and doesn't recommend it for production. Acceptable for this audience; moving to a custom domain later only changes `R2_PUBLIC_BASE_URL`.
