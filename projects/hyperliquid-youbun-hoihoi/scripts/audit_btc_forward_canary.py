from __future__ import annotations

import argparse
import json
from pathlib import Path

from hoihoi.btc_forward import audit_canary_overlap


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_canary_overlap(args.output)
    print(json.dumps(report, indent=2))
    if report["quality_gate"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
