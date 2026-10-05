from __future__ import annotations

import json
import os
import re
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .api import INFO_URL
from .forward_order import canonical_first_seen, envelope_rows, payload_for, unique_position_chain


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


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _after_position(row: dict) -> Decimal:
    payload = payload_for(row["source_endpoint"], row["payload"])
    before = Decimal(str(payload.get("startPosition") or "0"))
    size = Decimal(str(payload.get("sz") or "0"))
    return before + (size if payload.get("side") == "B" else -size)


def audit_canary_overlap(output: Path) -> dict:
    """Fail closed unless two successful, stateful canary polls are auditable."""
    run_dirs = sorted(output.glob("raw/date=*/run=*"))
    reasons: list[str] = []
    if len(run_dirs) != 2:
        reasons.append("RUN_COUNT_NOT_TWO")

    manifests = [json.loads((path / "manifest.json").read_text()) for path in run_dirs]
    if any(item.get("quality_gate") != "PASS" for item in manifests):
        reasons.append("COLLECTOR_GATE_FAILED")
    if len(manifests) == 2:
        first, second = manifests
        if first.get("wallet") != second.get("wallet"):
            reasons.append("WALLET_CHANGED")
        if first.get("analysis_start_ms") != second.get("analysis_start_ms"):
            reasons.append("ANALYSIS_START_CHANGED")
        if not (second.get("start_ms", 0) <= first.get("end_ms", -1) < second.get("end_ms", 0)):
            reasons.append("OVERLAP_WINDOW_INVALID")

    rows: list[dict] = []
    per_run: list[dict] = []
    for run_dir in run_dirs:
        run_rows: list[dict] = []
        missing = []
        for endpoint in ENDPOINTS:
            path = run_dir / f"{endpoint}.jsonl"
            if not path.exists():
                missing.append(endpoint)
                continue
            run_rows.extend(_read_jsonl(path))
        candle_path = run_dir / "btc_5m.jsonl"
        candles = _read_jsonl(candle_path) if candle_path.exists() else []
        if missing:
            reasons.append("RAW_SOURCE_MISSING")
        if not candles:
            reasons.append("ENTRY_PRE_MARKET_WINDOW_MISSING")
        sequences = [int(row["source_sequence"]) for row in run_rows]
        sequence_ok = sequences == list(range(len(sequences)))
        if not sequence_ok:
            reasons.append("SOURCE_SEQUENCE_INVALID")
        response_order_ok = True
        grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
        for row in run_rows:
            grouped[(row["source_endpoint"], int(row["page_index"]))].append(int(row["row_index"]))
        for indexes in grouped.values():
            if indexes != list(range(len(indexes))):
                response_order_ok = False
        if not response_order_ok:
            reasons.append("API_RESPONSE_ORDER_INVALID")
        rows.extend(run_rows)
        per_run.append({
            "run_id": run_dir.name.removeprefix("run="),
            "raw_records": len(run_rows),
            "btc_5m_records": len(candles),
            "source_sequence_ok": sequence_ok,
            "api_response_order_ok": response_order_ok,
        })

    canonical = canonical_first_seen(rows)
    first_seen_ok = all(row is rows[next(
        index for index, raw in enumerate(rows)
        if (raw["source_endpoint"], raw["wallet"], raw["dedup_key"])
        == (row["source_endpoint"], row["wallet"], row["dedup_key"])
    )] for row in canonical)
    if not first_seen_ok:
        reasons.append("FIRST_SEEN_NOT_PRESERVED")

    # A TWAP slice can also appear in ordinary fills. Position-chain validation
    # therefore uses the first observed transaction id across both raw sources.
    btc_rows = []
    seen_tids = set()
    for row in canonical:
        payload = payload_for(row["source_endpoint"], row["payload"])
        if payload.get("coin") != "BTC":
            continue
        tid = payload.get("tid")
        key = ("tid", str(tid)) if tid is not None else (row["source_endpoint"], row["dedup_key"])
        if key not in seen_tids:
            seen_tids.add(key)
            btc_rows.append(row)
    by_time: dict[int, list[dict]] = defaultdict(list)
    for row in btc_rows:
        by_time[int(row["source_time_ms"])].append(row)
    expected = None
    ambiguous_times = []
    continuity_errors = 0
    for time_ms in sorted(by_time):
        chain = unique_position_chain(by_time[time_ms], expected)
        if chain is None:
            ambiguous_times.append(time_ms)
            expected = None
            continue
        if expected is not None:
            payload = payload_for(chain[0]["source_endpoint"], chain[0]["payload"])
            if Decimal(str(payload.get("startPosition") or "0")) != expected:
                continuity_errors += 1
        expected = _after_position(chain[-1])
    if ambiguous_times:
        reasons.append("POSITION_CHAIN_AMBIGUOUS")
    if continuity_errors:
        reasons.append("POSITION_CHAIN_DISCONTINUITY")

    state_path = output / "state" / "collector_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if len(manifests) == 2 and (
        state.get("last_run_id") != manifests[-1].get("run_id")
        or state.get("last_success_poll_ms") != manifests[-1].get("end_ms")
    ):
        reasons.append("STATE_NOT_AT_SECOND_SUCCESS")

    report = {
        "schema_version": 1,
        "audit_version": "btc-forward-v1-canary-overlap",
        "quality_gate": "PASS" if not reasons else "FAIL",
        "failure_reasons": sorted(set(reasons)),
        "run_count": len(run_dirs),
        "runs": per_run,
        "raw_records": len(rows),
        "canonical_records": len(canonical),
        "overlap_duplicates_retained_raw": len(rows) - len(canonical),
        "first_seen_preserved": first_seen_ok,
        "btc_position_rows": len(btc_rows),
        "ambiguous_same_ms_times": ambiguous_times,
        "position_continuity_errors": continuity_errors,
        "state_last_run_id": state.get("last_run_id"),
    }
    atomic_json(output / "canary_audit.json", report)
    return report


def collect_canary_cohort(api, config_path: Path, output: Path, now_ms: int) -> dict:
    """Collect an isolated, frozen, at-most-five-wallet 24h validation window."""
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    wallets = config.get("wallets") or []
    if not 1 <= len(wallets) <= 5:
        raise ValueError("canary cohort must contain 1 to 5 wallets")
    addresses = [str(item.get("wallet", "")).lower() for item in wallets]
    if len(set(addresses)) != len(addresses):
        raise ValueError("canary cohort contains duplicate wallets")
    if any(not re.fullmatch(r"0x[0-9a-f]{40}", wallet) for wallet in addresses):
        raise ValueError("canary cohort contains invalid wallet")
    window_hours = int(config.get("window_hours") or 0)
    if window_hours != 24:
        raise ValueError("canary cohort window_hours must be 24")
    config_sha = hashlib.sha256(config_bytes).hexdigest()
    state_path = output / "cohort_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    if state and state["config_sha256"] != config_sha:
        raise ValueError("canary cohort config changed after window start")
    analysis_start_ms = state["analysis_start_ms"] if state else now_ms
    window_end_ms = analysis_start_ms + window_hours * 60 * 60_000
    if now_ms > window_end_ms:
        return {
            "schema_version": 1,
            "cohort_id": config["cohort_id"],
            "quality_gate": "WINDOW_COMPLETE",
            "analysis_start_ms": analysis_start_ms,
            "window_end_ms": window_end_ms,
            "wallet_results": [],
        }

    results = []
    for wallet in addresses:
        wallet_output = output / "wallets" / wallet
        result = collect_canary(api, wallet, wallet_output, now_ms, initial_lookback_ms=0)
        results.append({
            "wallet": wallet,
            "run_id": result["run_id"],
            "quality_gate": result["quality_gate"],
            "endpoint_results": result["endpoint_results"],
            "market_result": result.get("market_result", {}),
            "state_advanced": result["state_advanced"],
        })
    quality_gate = "PASS" if all(item["quality_gate"] == "PASS" for item in results) else "FAIL"
    run_id = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "schema_version": 1,
        "collector_version": "btc-forward-v1-canary24h",
        "cohort_id": config["cohort_id"],
        "config_sha256": config_sha,
        "run_id": run_id,
        "quality_gate": quality_gate,
        "analysis_start_ms": analysis_start_ms,
        "window_end_ms": window_end_ms,
        "wallet_results": results,
        "automatic_sample_promotion": False,
    }
    atomic_json(output / "cohort_runs" / f"{run_id}.json", report)
    if quality_gate == "PASS":
        prior_runs = int(state.get("successful_run_count", 0)) if state else 0
        atomic_json(state_path, {
            "schema_version": 1,
            "cohort_id": config["cohort_id"],
            "config_sha256": config_sha,
            "analysis_start_ms": analysis_start_ms,
            "window_end_ms": window_end_ms,
            "last_success_poll_ms": now_ms,
            "last_run_id": run_id,
            "successful_run_count": prior_runs + 1,
        })
    return report
