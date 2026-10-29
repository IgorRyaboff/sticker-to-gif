## 1. ffmpeg on Vercel (de-risk first)

- [x] 1.1 Add `imageio-ffmpeg` and confirm that `get_ffmpeg_exe()` resolves a binary on Linux x86_64 — the manylinux wheel (0.7.0) ships a static ffmpeg 7.0.2 built with `--enable-libvpx`, and the binary contains the `libvpx-vp9` decoder
- [x] 1.2 Confirm on Vercel at runtime that a video sticker converts with transparency (folded into 6.3; no throwaway deployment needed after the check in 1.1)
- [x] 1.3 If `libvpx-vp9` is missing, switch to a vendored static ffmpeg build downloaded during the Vercel build — not needed (see 1.1)

## 2. Shared package

- [x] 2.1 Create `src/sticker_bot/` and move `convert.py` and `storage.py` from `src/poc`
- [x] 2.2 Resolve the ffmpeg executable in `convert.py`: system `ffmpeg` on PATH, otherwise `imageio_ffmpeg.get_ffmpeg_exe()`, copied to `/tmp` if the bundle dropped its exec bit
- [x] 2.3 Extract the Bot API client (`tg`, `reply`, `download`) into `telegram.py`, reading the token lazily from the environment
- [x] 2.4 Extract `classify()`, `handle(message, store)`, and the never-raising `handle_update(update, store)` into `handler.py`; reply with the link only on cache hits, and with link + stats on new conversions
- [x] 2.5 Add a strict store factory (`require_r2_store()`) that raises a configuration error when any R2 variable is missing

## 3. Vercel webhook

- [x] 3.1 Create `api/webhook.py` (BaseHTTPRequestHandler) that adds `src/` to `sys.path`, checks the secret header with `hmac.compare_digest` (`401` on mismatch or unset secret), parses the update, and calls `handle_update()`; missing R2 config → logged `500`
- [x] 3.2 Catch handler exceptions: log them, send the "conversion failed" reply on a best-effort basis, and always respond `200` to authenticated requests
- [x] 3.3 Add a root `requirements.txt` and a `vercel.json` with `maxDuration = 60` and `excludeFiles`; keep `.env`, `.venv`, tests and openspec out of uploads with `.vercelignore`
- [x] 3.4 Add `scripts/set_webhook.py <url>`, which calls `setWebhook` with `secret_token`, `allowed_updates=["message"]`, and `drop_pending_updates=true`, then prints `getWebhookInfo`

## 4. Local development

- [x] 4.1 Add `scripts/poll.py` using `handle_update()` and the lenient store factory (R2 or LocalStore); refuse to start when the token has a webhook set unless `--take-over` is passed
- [x] 4.2 Point `bootstrap.sh` at `scripts/poll.py`, a root `.venv`, and `requirements-dev.txt`; add a generated `TELEGRAM_WEBHOOK_SECRET` to `.env` with a comment that local runs should use a dev bot token
- [x] 4.3 Delete `src/poc` once `scripts/poll.py` matches its behavior

## 5. Tests

- [x] 5.1 Converter tests using generated fixtures (alpha WebM via ffmpeg overlay, minimal Lottie → TGS, MP4 testsrc, RGBA WebP): transparency, no ghosting, total duration, MP4 scaling and fps caps
- [x] 5.2 `classify()` tests for each message type, including `animation` + `document` precedence and the unsupported case
- [x] 5.3 Webhook handler tests: missing/wrong/unset secret → 401; valid update → 200; missing R2 config → 500; handler exception → failure reply without raising
- [x] 5.4 Storage tests: endpoint selection with and without `R2_JURISDICTION`, upload headers and public URL, 404 → cache miss, strict factory errors; cache hit skips download (in handler tests)

## 6. Deploy and verify

- [x] 6.1 Create the Vercel project (`sticker-to-gif`, fra1, Vercel Authentication on previews only) and set the production environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, all `R2_*`)
- [x] 6.2 Deploy to production and run `scripts/set_webhook.py https://sticker-to-gif-igor-9472.vercel.app/api/webhook`
- [x] 6.3 Send a static, animated, and video sticker, a Telegram GIF, and a repeat of one of them; confirm the replies, cache hit, and runtime logs
- [x] 6.4 Paste each resulting link into Bitrix24 and confirm it renders inline
