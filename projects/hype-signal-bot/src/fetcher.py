import time
from typing import Any

from shared.hyperliquid import HyperliquidClient
from shared.logging_utils import get_logger


INTERVAL_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


_client = HyperliquidClient(
    timeout_seconds=15,
    user_agent="base-lab-hype-signal-bot/0.1",
    logger=get_logger("hype-signal-bot"),
)


def _post(payload: dict[str, Any]) -> Any:
    return _client.post_info(payload)


def get_asset_ctx(coin: str = "HYPE") -> dict[str, Any] | None:
    return _client.asset_ctx(coin)


def get_candles(
    coin: str = "HYPE",
    interval: str = "1h",
    count: int = 48,
    *,
    only_closed: bool = True,
) -> list[dict[str, Any]]:
    interval_ms = INTERVAL_MS.get(interval)
    if interval_ms is None:
        raise ValueError(f"Unsupported interval: {interval}")

    now_ms = int(time.time() * 1000)
    end_time = now_ms
    if only_closed:
        end_time = (now_ms // interval_ms) * interval_ms - 1
    start_time = end_time - interval_ms * count

    return _post(
        {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
            },
        }
    )


def get_funding_history(coin: str = "HYPE", hours: int = 24) -> list[dict[str, Any]]:
    end_time = int(time.time() * 1000)
    start_time = end_time - hours * 60 * 60 * 1000
    return _post(
        {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_time,
            "endTime": end_time,
        }
    )
