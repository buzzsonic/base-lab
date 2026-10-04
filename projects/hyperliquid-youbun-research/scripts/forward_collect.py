from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from src.poc import INFO, get_json


SCHEMA_VERSION = 2
SAMPLE_VERSION = "pilot-100-v1"
COLLECTOR_VERSION = "forward-v2"
ENDPOINTS = {
    "fills": {"type": "userFillsByTime", "page_size": 2000, "cadence_ms": 20 * 60_000},
    "twap": {"type": "userTwapSliceFillsByTime", "page_size": 500, "cadence_ms": 20 * 60_000},
    "funding": {"type": "userFunding", "page_size": 500, "cadence_ms": 60 * 60_000},
}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def row_payload(endpoint: str, row: dict) -> dict:
    return dict(row.get("fill") or {}) if endpoint == "twap" else row


def source_time(endpoint: str, row: dict) -> int:
    return int(row_payload(endpoint, row).get("time") or row.get("time") or 0)


def dedup_key(endpoint: str, row: dict) -> str:
    payload = row_payload(endpoint, row)
    if payload.get("tid") is not None:
        return str(payload["tid"])
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fetch_pages(endpoint: str, wallet: str, start_ms: int, end_ms: int,
                page_delay_seconds: float, max_pages: int = 100) -> tuple[list[dict], int, bool]:
    config = ENDPOINTS[endpoint]
    cursor = start_ms
    rows: list[dict] = []
    seen: set[str] = set()
    requests = 0
    for _ in range(max_pages):
        payload = {"type": config["type"], "user": wallet, "startTime": cursor, "endTime": end_ms}
        if endpoint == "fills":
            payload["aggregateByTime"] = False
        batch = get_json(INFO, payload)
        requests += 1
        # Info calls cost 20 weight plus one per 20 returned items. Staying at
        # or below 600 weight/minute leaves 50% headroom under the IP limit.
        if page_delay_seconds > 0:
            weight = 20 + math.ceil(len(batch) / 20)
            time.sleep(max(page_delay_seconds, weight / 10))
        added = 0
        for row in batch:
            key = dedup_key(endpoint, row)
            if key not in seen:
                seen.add(key); rows.append(row); added += 1
        if len(batch) < config["page_size"]:
            return rows, requests, False
        next_cursor = max(source_time(endpoint, row) for row in batch)
        if next_cursor < cursor or added == 0:
            raise RuntimeError(f"{endpoint} pagination stalled at {cursor}")
        cursor = next_cursor
    return rows, requests, True


def load_sample(path: Path, max_wallets: int | None) -> list[dict]:
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 100:
        raise ValueError(f"frozen sample must contain 100 wallets, got {len(rows)}")
    if len({row["wallet"].lower() for row in rows}) != 100:
        raise ValueError("frozen sample contains duplicate wallets")
    return rows[:max_wallets] if max_wallets else rows


def collect(sample: Path, output: Path, now_ms: int, overlap_ms: int,
            request_delay_seconds: float, max_wallets: int | None = None,
            collector_version: str = COLLECTOR_VERSION) -> dict:
    accounts = load_sample(sample, max_wallets)
    state_path = output / "state" / "collector_state.json"
    sample_sha = hashlib.sha256(sample.read_bytes()).hexdigest()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["sample_sha256"] != sample_sha:
            raise ValueError("sampling manifest changed after collector start")
        if now_ms < state["analysis_start_ms"]:
            raise ValueError("run time precedes fixed analysis start")
    else:
        state = {"schema_version": SCHEMA_VERSION, "collector_version": collector_version,
                 "sample_version": SAMPLE_VERSION,
                 "sample_sha256": sample_sha, "analysis_start_ms": now_ms, "checkpoints": {}}
    run_id = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
    run_parent = output / "raw" / f"date={date}"
    run_dir = run_parent / f"run={run_id}"
    temporary_run_dir = run_parent / f".run={run_id}.tmp"
    if run_dir.exists():
        raise ValueError(f"immutable run already exists: {run_id}")
    temporary_run_dir.mkdir(parents=True)
    handles = {name: (temporary_run_dir / f"{name}.jsonl").open("w") for name in ENDPOINTS}
    manifest = {"schema_version": SCHEMA_VERSION, "collector_version": collector_version,
                "run_id": run_id, "analysis_start_ms": state["analysis_start_ms"],
                "started_at_ms": now_ms, "requested_wallets": len(accounts), "endpoint_results": [],
                "failures": 0, "retention_risks": 0, "cap_hits": 0,
                "records": 0, "requests": 0}
    try:
        for account in accounts:
            wallet = account["wallet"].lower()
            for endpoint, config in ENDPOINTS.items():
                key = f"{wallet}|{endpoint}"
                checkpoint = state["checkpoints"].setdefault(key, {"consecutive_failures": 0, "requests": 0, "records": 0})
                last_poll = checkpoint.get("last_success_poll_ms")
                if last_poll is not None and now_ms - last_poll < config["cadence_ms"]:
                    continue
                start_ms = max(state["analysis_start_ms"], (last_poll or state["analysis_start_ms"]) - overlap_ms)
                result = {"anon_wallet_id": account["anon_wallet_id"], "endpoint": endpoint, "start_ms": start_ms}
                try:
                    rows, requests, cap_hit = fetch_pages(endpoint, wallet, start_ms, now_ms,
                                                          request_delay_seconds)
                    ingested_at = datetime.now(timezone.utc).isoformat()
                    for row in rows:
                        envelope = {"schema_version": SCHEMA_VERSION, "sample_version": SAMPLE_VERSION,
                                    "wallet": wallet, "anon_wallet_id": account["anon_wallet_id"],
                                    "source_endpoint": config["type"], "source_time": source_time(endpoint, row),
                                    "ingested_at": ingested_at, "run_id": run_id,
                                    "dedup_key": dedup_key(endpoint, row), "payload": row}
                        handles[endpoint].write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
                    latest = max((source_time(endpoint, row) for row in rows), default=checkpoint.get("last_source_time_ms"))
                    retention_risk = endpoint == "fills" and len(rows) >= 10_000
                    checkpoint.update({"last_success_poll_ms": now_ms, "last_source_time_ms": latest,
                                       "last_status": "success", "last_error": None, "consecutive_failures": 0,
                                       "requests": checkpoint["requests"] + requests,
                                       "records": checkpoint["records"] + len(rows),
                                       "page_safety_cap_hit": cap_hit,
                                       "retention_risk": retention_risk})
                    result.update({"status": "success", "records": len(rows), "requests": requests,
                                   "page_safety_cap_hit": cap_hit, "retention_risk": retention_risk})
                    manifest["records"] += len(rows); manifest["requests"] += requests
                    manifest["retention_risks"] += int(retention_risk)
                    manifest["cap_hits"] += int(cap_hit)
                except Exception as exc:
                    checkpoint.update({"last_status": "failed", "last_error": str(exc),
                                       "consecutive_failures": checkpoint.get("consecutive_failures", 0) + 1})
                    result.update({"status": "failed", "error": str(exc)})
                    manifest["failures"] += 1
                manifest["endpoint_results"].append(result)
    finally:
        for handle in handles.values():
            handle.close()
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(temporary_run_dir / "manifest.json", manifest)
    temporary_run_dir.replace(run_dir)
    quality_gate_failed = manifest["failures"] > 0 or manifest["retention_risks"] > 0 or manifest["cap_hits"] > 0
    if not quality_gate_failed:
        atomic_json(state_path, state)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now-ms", type=int)
    parser.add_argument("--overlap-minutes", type=int, default=20)
    parser.add_argument("--request-delay-seconds", type=float, default=2.2)
    parser.add_argument("--max-wallets", type=int)
    parser.add_argument("--collector-version", default=COLLECTOR_VERSION)
    args = parser.parse_args()
    now_ms = args.now_ms if args.now_ms is not None else int(time.time() * 1000)
    result = collect(args.sample, args.output, now_ms, args.overlap_minutes * 60_000,
                     args.request_delay_seconds, args.max_wallets, args.collector_version)
    quality_gate_failed = result["failures"] > 0 or result["retention_risks"] > 0 or result["cap_hits"] > 0
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with Path(github_output).open("a") as handle:
            handle.write(f"quality_gate_failed={str(quality_gate_failed).lower()}\n")
    print(json.dumps({key: result[key] for key in ("run_id", "requested_wallets", "requests", "records", "failures")}, indent=2))
    if quality_gate_failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
