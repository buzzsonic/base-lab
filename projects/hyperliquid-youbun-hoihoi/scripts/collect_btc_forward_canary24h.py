from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from hoihoi.api import PublicApi
from hoihoi.btc_forward import collect_canary_cohort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now-ms", type=int)
    args = parser.parse_args()
    api = PublicApi(args.output / "http-cache", min_interval=2.2)
    report = collect_canary_cohort(
        api, args.config, args.output,
        args.now_ms if args.now_ms is not None else int(time.time() * 1000),
    )
    print(json.dumps(report, indent=2))
    if report["quality_gate"] == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
