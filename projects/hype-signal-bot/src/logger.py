import logging
from datetime import timezone, timedelta


JST = timezone(timedelta(hours=9))


def get_logger() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("hype-signal-bot")
