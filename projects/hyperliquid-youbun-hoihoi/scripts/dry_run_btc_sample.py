from __future__ import annotations

import argparse
import json
from pathlib import Path

from hoihoi.btc_dry_run import run_dry_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_dry_run(args.current, args.shadow, args.output), indent=2))


if __name__ == "__main__":
    main()
