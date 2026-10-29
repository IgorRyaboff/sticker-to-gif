## Context

A local POC in `src/poc` (Python, Telegram long polling) works end to end against the real bot and R2 bucket:

- `convert.py`: Pillow for WebP → PNG; rlottie renders TGS frames, then ffmpeg encodes them to GIF; ffmpeg converts WebM (forcing the `libvpx-vp9` decoder) and MP4 to GIF using palettegen/paletteuse.
- `storage.py`: boto3 against R2's S3 API. Keys are `<file_unique_id>.<ext>`; `HEAD` checks for a cached copy; the bucket is in the EU jurisdiction, so the endpoint is `<account>.eu.r2.cloudflarestorage.com`.
- `bot.py`: classifies the message, downloads it with `getFile`, converts, uploads, and replies with the link plus size and conversion time.

Measured locally: conversions take 0.1–0.4 s for typical stickers. The output GIFs keep transparency, don't ghost, and have the correct total duration.

Constraints:
- Vercel Functions only, no always-on process, so the bot must use webhook mode.
- No Cloudflare-managed domain, so links use the bucket's `r2.dev` public URL.
- The consumer is Bitrix24, which only renders an image when given a link that returns a real image content type.

## Goals / Non-Goals

**Goals:**
- Same conversion behavior as the POC, running as a Vercel Python Function triggered by Telegram webhooks.
- One codebase for both production (webhook) and local development (polling).
- Links that never change and never expire; repeated inputs don't trigger new work.
- Safe under Telegram webhook retries.

**Non-Goals:**
- Access control, quotas, or rate limiting.
- Whole sticker packs, albums, custom emoji in text, photos, or videos with audio.
- Output formats other than PNG/GIF (no WebP, APNG, or MP4 links).
- A custom domain or CDN in front of R2.
- Deleting stored objects or managing a lifecycle for them.

## Decisions

### 1. Stay on Python
rlottie-python is the only practical TGS renderer that's a plain package install (manylinux wheels include `librlottie`). Node would need headless Chromium with lottie-web, or an unproven WASM renderer.
*Alternative considered:* TypeScript with sharp and ffmpeg-static. Rejected because TGS would have no solution.

### 2. Ship ffmpeg inside the function bundle
Vercel's Python runtime has no system ffmpeg. Use the `imageio-ffmpeg` package, which ships a static Linux x86_64 ffmpeg binary, and find it with `imageio_ffmpeg.get_ffmpeg_exe()`. Use the system `ffmpeg` on PATH when it's present (local macOS).
**Must be verified before building on it:** the bundled build must include the `libvpx-vp9` decoder, or video stickers lose their transparency.
*Fallback:* vendor a johnvansickle static build (about 80 MB, includes libvpx) and download it during the Vercel build. Both options fit easily within the 500 MB Python bundle limit.

### 3. Convert synchronously inside the webhook request
The handler does all the work and replies to the user before returning `200`. Conversions take under a second for stickers and a few seconds for long MP4s. Set `maxDuration` to 60 s.
*Alternatives considered:*
- Return `200` immediately and finish in the background (`waitUntil`, or a queue). This adds moving parts with no benefit at this workload.
- Reply through the webhook's HTTP response (Telegram allows one method call in it). Rejected: it only works for a single call, and we already call `sendChatAction` and `getFile` before replying.

### 4. Always acknowledge the webhook; idempotency comes from the key
After the request is authenticated, the handler returns `200` even if the conversion failed (the user gets an error message instead), so Telegram doesn't retry indefinitely.
If Telegram does retry, for example after a timeout, the object key is `file_unique_id`, so the re-run either hits the cache or overwrites the same object with the same bytes. The worst case is a duplicate reply message, which is acceptable.
*Alternative considered:* deduplicating `update_id` in a KV store. Rejected: it adds infrastructure to prevent a harmless duplicate message.

### 5. Authenticate webhooks with Telegram's secret token
Register the webhook with `secret_token`. The handler compares `X-Telegram-Bot-Api-Secret-Token` using `hmac.compare_digest` and returns `401` when it doesn't match. This makes the endpoint safe to expose publicly, because it can't be used to make the bot spam users.

### 6. Project layout

```
api/webhook.py             Vercel function (BaseHTTPRequestHandler) → sticker_bot.handle(update)
src/sticker_bot/
  convert.py               from POC; ffmpeg path resolved per Decision 2
  storage.py               from POC (R2Store, LocalStore, jurisdiction)
  telegram.py              thin Bot API client (tg(), reply(), download())
  handler.py               classify() + handle(message); shared by webhook and polling
scripts/poll.py            local long-polling runner (replaces src/poc/bot.py)
scripts/set_webhook.py     setWebhook with url + secret_token + allowed_updates=["message"]
requirements.txt           root; Vercel installs from here
vercel.json                functions["api/webhook.py"]: maxDuration 60
bootstrap.sh, .env         local workflow, now runs scripts/poll.py
```

`api/webhook.py` puts `src/` on `sys.path`. Vercel only builds functions from `api/`, and adding `src` to the path is simpler than making the package installable. All temporary files go under `tempfile` (which is `/tmp` on Vercel, the only writable path).
*Alternative considered:* FastAPI or Flask as the entrypoint. Rejected: there's only one route, so a framework adds nothing.

### 7. Configuration is environment-only
The same variable names are used everywhere: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`, `R2_JURISDICTION`. On Vercel they're project environment variables; locally they come from `.env`. When the R2 variables are missing, `LocalStore` stays the fallback for local use only. The webhook entrypoint refuses to start without R2 configured.

### 8. Conversion parameters carry over from the POC
- Static stickers: PNG, never JPG, because stickers depend on transparency.
- GIF frame rate is capped at 50 fps, because browsers slow down frame delays shorter than 2 cs.
- Transparent GIFs use `palettegen=reserve_transparent=1` and `paletteuse=alpha_threshold=128`.
- MP4: 15 fps, at most 480 px wide, first 30 s only, Bayer dithering.

## Risks / Trade-offs

- **The bundled ffmpeg may lack `libvpx-vp9`.** → Verify it in the first task with a real alpha WebM in a Vercel deployment. Switch to the vendored static build if it's missing.
- **`r2.dev` is rate-limited, and Cloudflare doesn't recommend it for production.** → Fine for a handful of friends. A custom domain later only changes `R2_PUBLIC_BASE_URL`, but existing links stay on `r2.dev`, so they keep working but don't move to the new domain.
- **Bitrix24 might proxy or cache images, or reject `r2.dev`.** → Already confirmed working with the POC. Nothing else is needed.
- **Public bot with no limits; anyone who finds it can fill the bucket.** → R2 storage is cheap, inputs are capped at 20 MB, and output is bounded by the MP4 limits. Revisit if abuse shows up.
- **Local polling would delete the production webhook (`getUpdates` needs `deleteWebhook`).** → Use a separate dev bot token in the local `.env`. `scripts/poll.py` warns when the token it's using currently has a webhook set.
- **Long MP4s can approach the time limit on a cold start.** → The 30 s / 15 fps / 480 px caps keep ffmpeg work to a few seconds; `maxDuration` 60 leaves headroom.
- **GIF transparency is 1-bit, so soft sticker edges look jagged.** → This is a limit of the format, and Bitrix24 needs GIF. `alpha_threshold` can be tuned if needed.

## Migration Plan

1. Create the Vercel project and set the environment variables in Production.
2. Deploy, then run `scripts/set_webhook.py https://<project>.vercel.app/api/webhook`.
3. Send one input of each type and check that every link renders in Bitrix24.
4. **Rollback:** `deleteWebhook`, then run the local poller with the production token.

Existing R2 objects from the POC stay valid, because the keys and URL format are identical.

## Open Questions

- Does `imageio-ffmpeg`'s Linux build include `libvpx-vp9`? The first task answers this.
- Should replies keep showing size and conversion time, or show just the link? Defaulting to keeping them; they're useful while friends try it.
