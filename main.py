"""FreeGPT entry point."""

from __future__ import annotations

import logging
import sys

import config
from bot.telegram_bot import run

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Copy .env.example to .env and fill in the values."
        )
        sys.exit(1)

    logger.info("FreeGPT starting – model=%s", config.OLLAMA_MODEL)
    run()


if __name__ == "__main__":
    main()
