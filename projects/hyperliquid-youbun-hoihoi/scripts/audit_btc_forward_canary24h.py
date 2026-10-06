from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from hoihoi.btc_forward import audit_canary_cohort24h


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit-at-ms", type=int)
    args = parser.parse_args()
    report = audit_canary_cohort24h(
        args.output, args.audit_at_ms if args.audit_at_ms is not None else int(time.time() * 1000)
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    if report["decision"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
