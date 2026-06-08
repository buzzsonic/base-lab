import time
from typing import Any

import requests


HL_API = "https://api.hyperliquid.xyz/info"

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


def _post(payload: dict[str, Any]) -> Any:
    response = requests.post(HL_API, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def get_asset_ctx(coin: str = "HYPE") -> dict[str, Any] | None:
    data = _post({"type": "metaAndAssetCtxs"})
    universe = data[0]["universe"]
    ctxs = data[1]
    for index, asset in enumerate(universe):
        if asset["name"] == coin:
            return ctxs[index]
    return None


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
