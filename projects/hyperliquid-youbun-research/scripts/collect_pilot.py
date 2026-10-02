from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.poc import fetch_fills, fetch_funding, fetch_twap_fills


ENDPOINTS = ("fills", "twap", "funding")


def load_rows(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def collect(manifest: Path, output: Path, start_ms: int, end_ms: int,
            delay_seconds: float = 1.0, page_delay_seconds: float = 1.5) -> dict:
    rows = load_rows(manifest)
    raw = output / "raw"
    checkpoints = output / "checkpoints"
    raw.mkdir(parents=True, exist_ok=True)
    checkpoints.mkdir(parents=True, exist_ok=True)
    run = {
        "schema_version": 1, "sample_version": "pilot-100-v1",
        "start_ms": start_ms, "end_ms": end_ms, "requested_wallets": len(rows),
        "wallets": {}, "started_at": datetime.now(timezone.utc).isoformat(),
    }
    run_path = output / "collection_manifest.json"
    if run_path.exists():
        prior = json.loads(run_path.read_text())
        if prior.get("start_ms") != start_ms or prior.get("end_ms") != end_ms:
            raise ValueError("checkpoint window differs; use a new output directory")
        run = prior
    for index, row in enumerate(rows, 1):
        wallet = row["wallet"].lower()
        state = run["wallets"].setdefault(wallet, {"endpoints": {}, "retries": 0, "failures": []})
        for endpoint in ENDPOINTS:
            if state["endpoints"].get(endpoint, {}).get("status") == "success":
                continue
            try:
                if endpoint == "fills":
                    result = fetch_fills(wallet, start_ms, end_ms, raw, page_delay_seconds)
                    details = {"rows": len(result), "pagination_safety_cap_hit": len(result) >= 200_000}
                elif endpoint == "twap":
                    result = fetch_twap_fills(wallet, start_ms, end_ms, raw)
                    details = {"rows": len(result), "endpoint_cap_hit": len(result) >= 2000}
                else:
                    result = fetch_funding(wallet, start_ms, end_ms, raw, page_delay_seconds)
                    details = {"rows": len(result), "pagination_safety_cap_hit": len(result) >= 50_000}
                state["endpoints"][endpoint] = {
                    "status": "success", "last_success_timestamp": datetime.now(timezone.utc).isoformat(), **details,
                }
            except Exception as exc:
                state["endpoints"][endpoint] = {"status": "failed", "error": str(exc)}
                state["failures"].append({"endpoint": endpoint, "error": str(exc)})
            state["complete"] = all(state["endpoints"].get(name, {}).get("status") == "success" for name in ENDPOINTS)
            save(checkpoints / f"{wallet}.json", state)
            save(run_path, run)
            time.sleep(delay_seconds)
        print(f"[{index}/{len(rows)}] {row['anon_wallet_id']} complete={state['complete']}", flush=True)
    run["finished_at"] = datetime.now(timezone.utc).isoformat()
    run["completed_wallets"] = sum(item.get("complete", False) for item in run["wallets"].values())
    run["failed_wallets"] = sum(bool(item.get("failures")) for item in run["wallets"].values())
    save(run_path, run)
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--page-delay-seconds", type=float, default=1.5)
    args = parser.parse_args()
    start_ms = args.end_ms - int(timedelta(days=args.days).total_seconds() * 1000)
    result = collect(args.manifest, args.output, start_ms, args.end_ms,
                     args.delay_seconds, args.page_delay_seconds)
    print(json.dumps({key: result.get(key) for key in ("requested_wallets", "completed_wallets", "failed_wallets")}, indent=2))


if __name__ == "__main__":
    main()
