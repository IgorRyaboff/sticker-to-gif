"""Local long-polling runner, for development without a public URL.

getUpdates only works with the webhook removed, so running this against the
production bot would take it offline. Use a separate dev bot token; pass
--take-over to delete an existing webhook anyway.
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sticker_bot.handler import handle_update  # noqa: E402
from sticker_bot.storage import LocalStore, make_store  # noqa: E402
from sticker_bot.telegram import tg  # noqa: E402

log = logging.getLogger("poll")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("botocore").setLevel(logging.WARNING)

    if webhook := tg("getWebhookInfo").get("url"):
        if "--take-over" not in sys.argv:
            sys.exit(
                f"This bot has a webhook set ({webhook}); polling would disable it.\n"
                "Use a dev bot token, or rerun with --take-over."
            )
        log.warning("removing webhook %s", webhook)
    tg("deleteWebhook")

    store = make_store()
    if isinstance(store, LocalStore):
        log.warning("R2 is not configured; saving files to %s", store.dir)
    log.info("polling as @%s", tg("getMe")["username"])

    offset = None
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=50, allowed_updates=["message"])
        except Exception:
            log.exception("getUpdates failed")
            time.sleep(3)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            handle_update(update, store)


if __name__ == "__main__":
    main()
