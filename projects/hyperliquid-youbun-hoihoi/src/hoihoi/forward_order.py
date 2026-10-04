from __future__ import annotations

import hashlib
import json
from decimal import Decimal


def payload_for(endpoint: str, row: dict) -> dict:
    return dict(row.get("fill") or {}) if endpoint == "twap" else row


def dedup_key(endpoint: str, row: dict) -> str:
    payload = payload_for(endpoint, row)
    if payload.get("tid") is not None:
        return str(payload["tid"])
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def envelope_rows(endpoint: str, wallet: str, rows: list[dict], run_id: str,
                  page_index: int, sequence_start: int = 0) -> list[dict]:
    """Preserve API response order; never sort equal-timestamp rows."""
    output = []
    for row_index, row in enumerate(rows):
        payload = payload_for(endpoint, row)
        output.append({
            "schema_version": 1,
            "collector_version": "btc-forward-v1",
            "run_id": run_id,
            "wallet": wallet.lower(),
            "source_endpoint": endpoint,
            "source_time_ms": int(payload.get("time") or row.get("time") or 0),
            "page_index": page_index,
            "row_index": row_index,
            "source_sequence": sequence_start + row_index,
            "dedup_key": dedup_key(endpoint, row),
            "payload": row,
        })
    return output


def canonical_first_seen(rows: list[dict]) -> list[dict]:
    """Deduplicate without replacing or reordering the first observed row."""
    seen = set()
    output = []
    for row in rows:
        key = (row["source_endpoint"], row["wallet"], row["dedup_key"])
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def _before_after(row: dict) -> tuple[Decimal, Decimal]:
    payload = payload_for(row["source_endpoint"], row["payload"])
    before = Decimal(str(payload.get("startPosition") or "0"))
    size = Decimal(str(payload.get("sz") or "0"))
    after = before + (size if payload.get("side") == "B" else -size)
    return before, after


def unique_position_chain(rows: list[dict], expected_before: Decimal | None = None) -> list[dict] | None:
    """Return the unique startPosition chain, or None for zero/multiple solutions."""
    if len(rows) <= 1:
        return list(rows)
    solutions: list[list[dict]] = []

    def visit(prefix: list[dict], remaining: list[dict]) -> None:
        if len(solutions) > 1:
            return
        if not remaining:
            solutions.append(prefix)
            return
        expected = _before_after(prefix[-1])[1] if prefix else expected_before
        for index, candidate in enumerate(remaining):
            before, _ = _before_after(candidate)
            if expected is None or before == expected:
                visit(prefix + [candidate], remaining[:index] + remaining[index + 1:])

    visit([], list(rows))
    return solutions[0] if len(solutions) == 1 else None
