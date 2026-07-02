from shared.logging_utils import JST, UTC, ActionLogger  # noqa: F401


def get_logger(name: str = "hyperliquid-wallet-report") -> ActionLogger:
    return ActionLogger(name)
