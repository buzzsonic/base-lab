from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from src.poc import INFO, get_json


def collect(episodes_csv: Path, output: Path, start_ms: int, end_ms: int, delay_seconds: float) -> dict:
    with episodes_csv.open() as handle:
        episodes = list(csv.DictReader(handle))
    coins = sorted({row["coin"] for row in episodes} | {"BTC"})
    output.mkdir(parents=True, exist_ok=True)
    snapshot_path = output / "meta_and_asset_ctxs.json"
    if not snapshot_path.exists():
        snapshot_path.write_text(json.dumps(get_json(INFO, {"type": "metaAndAssetCtxs"}), ensure_ascii=False))
    rows = []
    for index, coin in enumerate(coins, 1):
        path = output / f"candles_5m_{coin}.json"
        try:
            if path.exists():
                candles = json.loads(path.read_text())
            else:
                candles = get_json(INFO, {"type": "candleSnapshot", "req": {
                    "coin": coin, "interval": "5m", "startTime": start_ms, "endTime": end_ms,
                }})
                path.write_text(json.dumps(candles, ensure_ascii=False))
                time.sleep(delay_seconds)
            first = min((int(row["t"]) for row in candles), default=None)
            last = max((int(row["T"]) for row in candles), default=None)
            rows.append({"coin": coin, "status": "success", "candles": len(candles),
                         "first_open_ms": first, "last_close_ms": last,
                         "full_requested_window": bool(first is not None and first <= start_ms and last is not None and last >= end_ms)})
        except Exception as exc:
            rows.append({"coin": coin, "status": "failed", "candles": 0,
                         "first_open_ms": None, "last_close_ms": None,
                         "full_requested_window": False, "error": str(exc)})
        print(f"[{index}/{len(coins)}] {coin} {rows[-1]['status']}", flush=True)
    manifest = {"start_ms": start_ms, "end_ms": end_ms, "requested_coins": len(coins),
                "completed_coins": sum(row["status"] == "success" for row in rows),
                "failed_coins": sum(row["status"] != "success" for row in rows), "series": rows}
    (output / "coverage.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--delay-seconds", type=float, default=.5)
    args = parser.parse_args()
    result = collect(args.episodes, args.output, args.start_ms, args.end_ms, args.delay_seconds)
    print(json.dumps({k: result[k] for k in ("requested_coins", "completed_coins", "failed_coins")}, indent=2))


if __name__ == "__main__":
    main()
