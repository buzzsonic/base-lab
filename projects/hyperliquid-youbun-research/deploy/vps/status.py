import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    start = datetime.fromisoformat(args.started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(args.finished_at.replace("Z", "+00:00"))
    record = {
        "event": "collector_run",
        "run_id": manifest["run_id"],
        "started_at": args.started_at,
        "finished_at": args.finished_at,
        "duration_seconds": int((finish - start).total_seconds()),
        "wallet_count": manifest["requested_wallets"],
        "endpoint_count": len(manifest["endpoint_results"]),
        "failures": manifest["failures"],
        "cap_hits": manifest["cap_hits"],
        "retention_risks": manifest["retention_risks"],
        "exit_code": args.exit_code,
    }
    print(json.dumps(record, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
