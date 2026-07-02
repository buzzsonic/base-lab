from shared.logging_utils import JST, ActionLogger  # noqa: F401


def get_logger(name: str = "hyperliquid-alert") -> ActionLogger:
    return ActionLogger(name)
