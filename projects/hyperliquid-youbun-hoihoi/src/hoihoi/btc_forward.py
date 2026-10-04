from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .api import INFO_URL
from .forward_order import envelope_rows


ENDPOINTS = {
    "fills": {"type": "userFillsByTime", "limit": 2000},
    "twap": {"type": "userTwapSliceFillsByTime", "limit": 500},
}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def fetch_ranges(api, endpoint: str, wallet: str, start_ms: int, end_ms: int,
                 max_requests: int = 100) -> tuple[list[list[dict]], int, list[list[int]]]:
    """Split capped time ranges while preserving every API response row order."""
    config = ENDPOINTS[endpoint]
    pending = [(start_ms, end_ms)]
    pages: list[list[dict]] = []
    gaps: list[list[int]] = []
    requests = 0
    while pending:
        lo, hi = pending.pop(0)
        if requests >= max_requests:
            gaps.append([lo, hi])
            continue
        payload = {"type": config["type"], "user": wallet, "startTime": lo, "endTime": hi}
        if endpoint == "fills":
            payload["aggregateByTime"] = False
        batch = api.get_json(INFO_URL, payload)
        if not isinstance(batch, list):
            raise ValueError(f"{endpoint} returned non-list")
        requests += 1
        if len(batch) >= config["limit"]:
            if lo == hi:
                pages.append(batch)
                gaps.append([lo, hi])
            else:
                mid = (lo + hi) // 2
                pending[0:0] = [(lo, mid), (mid + 1, hi)]
        else:
            pages.append(batch)
    return pages, requests, gaps


def collect_canary(api, wallet: str, output: Path, now_ms: int,
                   initial_lookback_ms: int = 20 * 60_000,
                   overlap_ms: int = 20 * 60_000) -> dict:
    wallet = wallet.lower()
    if not re.fullmatch(r"0x[0-9a-f]{40}", wallet):
        raise ValueError("wallet must be a 20-byte hex address")
    state_path = output / "state" / "collector_state.json"
    prior = json.loads(state_path.read_text()) if state_path.exists() else None
    if prior and prior["wallet"] != wallet:
        raise ValueError("canary wallet cannot change after window start")
    analysis_start = prior["analysis_start_ms"] if prior else now_ms - initial_lookback_ms
    last_success = prior.get("last_success_poll_ms") if prior else None
    start_ms = max(analysis_start, (last_success - overlap_ms) if last_success else analysis_start)
    if now_ms < analysis_start:
        raise ValueError("now_ms precedes analysis_start_ms")

    run_id = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
    run_parent = output / "raw" / f"date={day}"
    run_dir = run_parent / f"run={run_id}"
    temporary = run_parent / f".run={run_id}.tmp"
    if run_dir.exists() or temporary.exists():
        raise ValueError(f"immutable run already exists: {run_id}")
    temporary.mkdir(parents=True)

    manifest = {
        "schema_version": 1, "collector_version": "btc-forward-v1-canary",
        "run_id": run_id, "wallet": wallet, "analysis_start_ms": analysis_start,
        "start_ms": start_ms, "end_ms": now_ms, "endpoint_results": {},
        "quality_gate": "PASS", "state_advanced": False,
    }
    sequence = 0
    try:
        for endpoint in ENDPOINTS:
            pages, requests, gaps = fetch_ranges(api, endpoint, wallet, start_ms, now_ms)
            path = temporary / f"{endpoint}.jsonl"
            records = 0
            with path.open("w") as handle:
                for page_index, page in enumerate(pages):
                    envelopes = envelope_rows(endpoint, wallet, page, run_id, page_index, sequence)
                    sequence += len(envelopes)
                    for envelope in envelopes:
                        envelope["response_received_at"] = datetime.now(timezone.utc).isoformat()
                        handle.write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
                    records += len(envelopes)
            manifest["endpoint_results"][endpoint] = {
                "requests": requests, "records": records, "gaps": gaps,
                "page_safety_cap_hit": bool(gaps),
            }
            if gaps:
                manifest["quality_gate"] = "FAIL"

        candle_payload = {"type": "candleSnapshot", "req": {
            "coin": "BTC", "interval": "5m", "startTime": max(0, now_ms - 2 * 60 * 60_000),
            "endTime": now_ms,
        }}
        candles = api.get_json(INFO_URL, candle_payload)
        if not isinstance(candles, list):
            raise ValueError("BTC candleSnapshot returned non-list")
        with (temporary / "btc_5m.jsonl").open("w") as handle:
            for index, candle in enumerate(candles):
                envelope = {"schema_version": 1, "source_endpoint": "candleSnapshot",
                            "coin": "BTC", "interval": "5m", "run_id": run_id,
                            "source_sequence": index, "payload": candle}
                handle.write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n")
        manifest["market_result"] = {"records": len(candles), "past_only_usage_policy": "filter candle close before episode entry"}
    except Exception as exc:
        manifest["quality_gate"] = "FAIL"
        manifest["error"] = str(exc)

    atomic_json(temporary / "manifest.json", manifest)
    temporary.replace(run_dir)
    if manifest["quality_gate"] == "PASS":
        state = {"schema_version": 1, "collector_version": "btc-forward-v1-canary",
                 "wallet": wallet, "analysis_start_ms": analysis_start,
                 "last_success_poll_ms": now_ms, "last_run_id": run_id}
        atomic_json(state_path, state)
        manifest["state_advanced"] = True
        atomic_json(run_dir / "manifest.json", manifest)
    return manifest
