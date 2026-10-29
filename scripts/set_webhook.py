"""Point the bot at a deployed webhook.

Usage: python scripts/set_webhook.py https://<project>.vercel.app/api/webhook
Needs TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET (the same secret as in Vercel).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sticker_bot.telegram import tg  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tg(
        "setWebhook",
        url=sys.argv[1],
        secret_token=os.environ["TELEGRAM_WEBHOOK_SECRET"],
        allowed_updates=["message"],
        drop_pending_updates=True,
    )
    print(json.dumps(tg("getWebhookInfo"), indent=2))


if __name__ == "__main__":
    main()
