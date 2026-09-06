"""coin-scout v2の永続観測ログと短期計算状態。"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path("data/observations")
STATE_PATH = Path(".state/collector_state.json")
HISTORY_RETENTION_MS = 26 * 60 * 60 * 1000


def event_id(exchange: str, symbol: str, observed_at_ms: int, version: str) -> str:
    bucket = observed_at_ms // 300_000
    raw = f"{version}|{exchange}|{symbol}|{bucket}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def load_collector_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_collector_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def append_unique_gzip(path: Path, records: list[dict[str, Any]], key: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict): existing.append(row)
                except json.JSONDecodeError:
                    continue
    seen = {str(row.get(key)) for row in existing}
    fresh = [row for row in records if str(row.get(key)) not in seen]
    if not fresh:
        return 0
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        for row in existing + fresh:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(fresh)


def observation_path(observed_at_ms: int) -> Path:
    stamp = datetime.fromtimestamp(observed_at_ms / 1000, timezone.utc)
    return DATA_DIR / stamp.strftime("%Y-%m-%d") / f"observations-{stamp.strftime('%H%M')}.jsonl.gz"


def outcome_path(observed_at_ms: int) -> Path:
    stamp = datetime.fromtimestamp(observed_at_ms / 1000, timezone.utc)
    return DATA_DIR / stamp.strftime("%Y-%m-%d") / f"outcomes-{stamp.strftime('%H%M')}.jsonl.gz"


def prune_history(history: dict[str, list[dict[str, Any]]], now_ms: int) -> None:
    cutoff = now_ms - HISTORY_RETENTION_MS
    for symbol in list(history):
        history[symbol] = [row for row in history[symbol] if row.get("observed_at_ms", 0) >= cutoff]
        if not history[symbol]: del history[symbol]


def build_outcomes(history: dict[str, list[dict[str, Any]]], now_ms: int, tolerance_minutes: int) -> list[dict[str, Any]]:
    results=[]; tolerance_ms=tolerance_minutes*60_000
    for symbol, rows in history.items():
        ordered=sorted(rows,key=lambda row:row["observed_at_ms"])
        for base in ordered:
            is_event=base.get("decision")=="fired"
            is_hourly_control=(base["observed_at_ms"]//300_000)%12==0
            if not is_event and not is_hourly_control:
                continue
            for horizon in (5,15,30,60):
                target=base["observed_at_ms"]+horizon*60_000
                if now_ms < target: continue
                endpoint=min(ordered,key=lambda row:abs(row["observed_at_ms"]-target))
                error=abs(endpoint["observed_at_ms"]-target)
                path=[row for row in ordered if base["observed_at_ms"] <= row["observed_at_ms"] <= endpoint["observed_at_ms"]]
                prices=[row.get("price") for row in path if row.get("price") is not None]
                base_price=base.get("price")
                status="observed" if error<=tolerance_ms and base_price not in (None,0) and prices else "missing"
                outcome_id=f"{base['event_id']}:{horizon}m"
                results.append({"outcome_id":outcome_id,"event_id":base["event_id"],"symbol":symbol,"sampling_role":"event" if is_event else "hourly_non_event_control","horizon_minutes":horizon,"status":status,"target_at_ms":target,"endpoint_at_ms":endpoint["observed_at_ms"] if status=="observed" else None,"timing_error_seconds":error/1000,"endpoint_return_pct":((endpoint.get("price")/base_price-1)*100 if status=="observed" else None),"max_rise_pct":((max(prices)/base_price-1)*100 if status=="observed" else None),"max_fall_pct":((min(prices)/base_price-1)*100 if status=="observed" else None),"path_event_ids":[row["event_id"] for row in path] if status=="observed" else [],"path_resolution":"observed snapshots, nominal 5m; no interpolation"})
    return results
