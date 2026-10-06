#!/usr/bin/env python3
"""Live adapter for market-core-v1. Public read-only; never submits orders."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request
from pathlib import Path

from forward_market_core_collect import collect_fixture, read_json

WS_URL = "wss://api.hyperliquid.xyz/ws"
INFO_URL = "https://api.hyperliquid.xyz/info"


def transform_message(message: dict, received_at_ms: int) -> list[dict]:
    channel, data = message.get("channel"), message.get("data")
    if channel == "activeAssetCtx" and data.get("coin") == "BTC":
        return [{"stream": "btc_asset_ctx", "received_at_ms": received_at_ms,
                 "source_time_ms": None, "source": "WS_ACTIVE_ASSET_CTX", "payload": data["ctx"]}]
    if channel == "candle" and data.get("s") == "BTC" and data.get("i") == "1m":
        return [{"stream": "btc_candle_1m", "received_at_ms": received_at_ms,
                 "source_time_ms": int(data["t"]), "source": "WS_CANDLE", "payload": data}]
    if channel == "trades":
        return [{"stream": "btc_trades", "received_at_ms": received_at_ms,
                 "source_time_ms": int(item["time"]), "source": "WS_TRADES", "payload": item}
                for item in data if item.get("coin") == "BTC"]
    return []


def fetch_candle_repairs(start_ms: int, end_ms: int) -> list[dict]:
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m",
                       "startTime": start_ms, "endTime": end_ms}}).encode()
    request = urllib.request.Request(INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        rows = json.load(response)
    received = int(time.time() * 1000)
    return [{"stream": "btc_candle_1m", "received_at_ms": received, "source_time_ms": int(item["t"]),
             "source": "REST_CANDLE_SNAPSHOT", "repair_source": "REST_CANDLE_SNAPSHOT", "payload": item}
            for item in rows]


async def run(output_root: Path, include_trades: bool, flush_seconds: int) -> None:
    import websockets  # installed only in the separate market-core image
    while True:
        try:
            state = read_json(output_root / "state.json", {})
            now = int(time.time() * 1000)
            pending = []
            last_candle = state.get("last_canonical_candle_t")
            if last_candle is not None and last_candle + 60_000 < now - 60_000:
                pending.extend(fetch_candle_repairs(last_candle + 60_000, now - 60_000))
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                subscriptions = [{"type": "activeAssetCtx", "coin": "BTC"},
                                 {"type": "candle", "coin": "BTC", "interval": "1m"}]
                if include_trades:
                    subscriptions.append({"type": "trades", "coin": "BTC"})
                for sub in subscriptions:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": sub}))
                pending.append({"stream": "collector_health", "received_at_ms": now,
                                "payload": {"event": "CONNECTION_OPEN"}})
                deadline = time.monotonic() + flush_seconds
                while True:
                    timeout = max(0.1, deadline - time.monotonic())
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        pending.extend(transform_message(json.loads(raw), int(time.time() * 1000)))
                    except asyncio.TimeoutError:
                        finished = int(time.time() * 1000)
                        run_id = str(finished)
                        pending.append({"stream": "collector_health", "received_at_ms": finished,
                                        "payload": {"event": "HEARTBEAT"}})
                        collect_fixture(pending, output_root, run_id, finished)
                        pending, deadline = [], time.monotonic() + flush_seconds
        except Exception as exc:
            print(json.dumps({"event": "reconnect", "error": type(exc).__name__}), flush=True)
            await asyncio.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--include-trades", action="store_true")
    parser.add_argument("--flush-seconds", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(run(args.output_root, args.include_trades, args.flush_seconds))


if __name__ == "__main__":
    main()
