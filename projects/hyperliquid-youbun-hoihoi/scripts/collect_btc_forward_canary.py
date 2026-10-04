from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from hoihoi.api import PublicApi
from hoihoi.btc_forward import collect_canary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now-ms", type=int)
    parser.add_argument("--initial-lookback-minutes", type=int, default=20)
    args = parser.parse_args()
    api = PublicApi(args.output / "http-cache", min_interval=2.2)
    result = collect_canary(api, args.wallet, args.output,
                            args.now_ms or int(time.time() * 1000),
                            args.initial_lookback_minutes * 60_000)
    print(json.dumps(result, indent=2))
    if result["quality_gate"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
