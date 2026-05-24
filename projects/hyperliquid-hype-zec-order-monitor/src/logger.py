import logging
from datetime import timedelta, timezone


JST = timezone(timedelta(hours=9), name="JST")


def get_logger() -> logging.Logger:
    logger = logging.getLogger("hyperliquid_hype_zec_order_monitor")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
