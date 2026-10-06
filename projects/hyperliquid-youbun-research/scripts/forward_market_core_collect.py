#!/usr/bin/env python3
"""Fixture-first storage engine for BTC forward market core v1.

This entrypoint intentionally has no network or VPS integration. It accepts
JSONL observations and exercises the same raw, canonical, gap and checkpoint
rules required before a live canary may be considered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


VERSION = "market-core-v1"
SCHEMA_VERSION = "forward-market-core-row-v1.0.0"
CORE_STREAMS = {"btc_asset_ctx", "btc_candle_1m"}
OPTIONAL_STREAMS = {"btc_trades"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any], sequence: int) -> dict[str, Any]:
    stream = row.get("stream")
    if stream not in CORE_STREAMS | OPTIONAL_STREAMS:
        raise ValueError(f"unknown stream: {stream}")
    received = row.get("received_at_ms")
    if not isinstance(received, int) or received < 0:
        raise ValueError("received_at_ms must be a non-negative integer")
    payload = row.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    source_time = row.get("source_time_ms")
    if source_time is not None and not isinstance(source_time, int):
        raise ValueError("source_time_ms must be integer or null")
    dedup = row.get("dedup_key")
    if not dedup:
        if stream == "btc_trades" and payload.get("tid") is not None:
            dedup = str(payload["tid"])
        else:
            dedup = payload_hash(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "collector_version": VERSION,
        "stream": stream,
        "source": row.get("source", "FIXTURE"),
        "coin": "BTC",
        "source_time_ms": source_time,
        "received_at_ms": received,
        "connection_id": row.get("connection_id", "fixture-connection"),
        "sequence_in_connection": row.get("sequence_in_connection", sequence),
        "is_snapshot": bool(row.get("is_snapshot", False)),
        "repair_source": row.get("repair_source"),
        "dedup_key": str(dedup),
        "payload": payload,
    }


def validate_asset_ctx(row: dict[str, Any]) -> None:
    required = {"markPx", "openInterest", "funding"}
    missing = required - set(row["payload"])
    if missing:
        raise ValueError(f"asset ctx missing: {sorted(missing)}")


def candle_record(row: dict[str, Any], run_finished_at_ms: int) -> dict[str, Any] | None:
    payload = row["payload"]
    for field in ("t", "T", "o", "h", "l", "c", "v"):
        if field not in payload:
            raise ValueError(f"candle missing: {field}")
    if int(payload["T"]) > run_finished_at_ms:
        return None
    return {
        "coin": "BTC",
        "interval": "1m",
        "t": int(payload["t"]),
        "T": int(payload["T"]),
        "o": payload["o"],
        "h": payload["h"],
        "l": payload["l"],
        "c": payload["c"],
        "v": payload["v"],
        "repair_source": row["repair_source"],
        "received_at_ms": row["received_at_ms"],
    }


def load_canonical(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            item = json.loads(line)
            records[int(item["t"])] = item
    return records


def gap_manifest(candles: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    times = sorted(candles)
    gaps = [
        {
            "stream": "btc_candle_1m",
            "start_ms": item["t"],
            "end_ms": item["t"],
            "missing_count": 1,
            "status": "RESOLVED_REST",
        }
        for item in candles.values()
        if item.get("repair_source") == "REST_CANDLE_SNAPSHOT"
    ]
    for previous, current in zip(times, times[1:]):
        expected = previous + 60_000
        if current > expected:
            gaps.append({
                "stream": "btc_candle_1m",
                "start_ms": expected,
                "end_ms": current - 60_000,
                "missing_count": (current - expected) // 60_000,
                "status": "UNRESOLVED",
            })
    return gaps


def collect_fixture(
    rows: Iterable[dict[str, Any]],
    output_root: Path,
    run_id: str,
    run_finished_at_ms: int,
    fail_before_checkpoint: bool = False,
) -> dict[str, Any]:
    """Persist one fixture run transactionally and return its manifest."""
    output_root.mkdir(parents=True, exist_ok=True)
    runs_dir = output_root / "runs"
    runs_dir.mkdir(exist_ok=True)
    final_run = runs_dir / run_id
    if final_run.exists():
        raise ValueError(f"run already exists: {run_id}")

    state_path = output_root / "state.json"
    canonical_path = output_root / "canonical_candles_1m.jsonl"
    prior_state = read_json(state_path, {"collector_version": VERSION, "last_successful_run_id": None})
    canonical = load_canonical(canonical_path)
    optional_errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    latest_ctx_ms = prior_state.get("last_asset_ctx_received_at_ms")

    for sequence, raw in enumerate(rows, start=1):
        try:
            row = normalize_row(raw, sequence)
            if row["stream"] == "btc_asset_ctx":
                validate_asset_ctx(row)
                latest_ctx_ms = max(latest_ctx_ms or 0, row["received_at_ms"])
            elif row["stream"] == "btc_candle_1m":
                candle = candle_record(row, run_finished_at_ms)
                if candle is not None:
                    existing = canonical.get(candle["t"])
                    if existing is None or candle["received_at_ms"] >= existing["received_at_ms"]:
                        canonical[candle["t"]] = candle
            normalized.append(row)
        except (TypeError, ValueError) as exc:
            if raw.get("stream") in OPTIONAL_STREAMS:
                optional_errors.append(str(exc))
                continue
            raise

    temp_run = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=runs_dir))
    try:
        by_stream: dict[str, list[dict[str, Any]]] = {}
        for row in normalized:
            by_stream.setdefault(row["stream"], []).append(row)
        for stream, stream_rows in by_stream.items():
            (temp_run / f"{stream}.jsonl").write_text(
                "".join(canonical_json(row) + "\n" for row in stream_rows), encoding="utf-8"
            )

        gaps = gap_manifest(canonical)
        stale = latest_ctx_ms is None or run_finished_at_ms - latest_ctx_ms > 120_000
        if stale:
            gaps.append({
                "stream": "btc_asset_ctx",
                "start_ms": latest_ctx_ms,
                "end_ms": run_finished_at_ms,
                "status": "STALE_INTERVAL",
            })
        manifest = {
            "collector_version": VERSION,
            "run_id": run_id,
            "run_finished_at_ms": run_finished_at_ms,
            "status": "PASS_WITH_OPTIONAL_ERRORS" if optional_errors else "PASS",
            "row_counts": {stream: len(values) for stream, values in sorted(by_stream.items())},
            "optional_errors": optional_errors,
            "unresolved_candle_gaps": sum(
                g["stream"] == "btc_candle_1m" and g["status"] == "UNRESOLVED" for g in gaps
            ),
            "asset_ctx_stale": stale,
        }
        write_json(temp_run / "gap_manifest.json", gaps)
        write_json(temp_run / "manifest.json", manifest)
        os.replace(temp_run, final_run)

        if fail_before_checkpoint:
            raise RuntimeError("injected failure before checkpoint")
        canonical_temp = output_root / ".canonical_candles_1m.jsonl.tmp"
        canonical_temp.write_text(
            "".join(canonical_json(canonical[t]) + "\n" for t in sorted(canonical)), encoding="utf-8"
        )
        os.replace(canonical_temp, canonical_path)
        next_state = {
            "collector_version": VERSION,
            "last_successful_run_id": run_id,
            "last_run_finished_at_ms": run_finished_at_ms,
            "last_asset_ctx_received_at_ms": latest_ctx_ms,
        }
        state_temp = output_root / ".state.json.tmp"
        write_json(state_temp, next_state)
        os.replace(state_temp, state_path)
        return manifest
    except Exception:
        if temp_run.exists():
            shutil.rmtree(temp_run)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-finished-at-ms", required=True, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [json.loads(line) for line in args.fixture.read_text(encoding="utf-8").splitlines() if line]
    manifest = collect_fixture(rows, args.output_root, args.run_id, args.run_finished_at_ms)
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
