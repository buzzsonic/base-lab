from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .storage import read_parquet, write_json


FLAGS = ("bot_suspected", "mm_suspected", "farm_suspected",
         "arbitrage_suspected", "funding_arbitrage_suspected")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def summarize_cohort(path: Path, as_of: datetime, minimum_days: int = 7) -> dict:
    registry = read_parquet(path / "wallet_registry.parquet")
    pool = read_parquet(path / "discovery_pool.parquet")
    sample = read_parquet(path / "research_sample.parquet")
    wallets = [str(row.get("wallet")) for row in registry]
    active_wallets = {str(row.get("wallet")) for row in registry if row.get("status") == "ACTIVE"}
    sample_wallets = {str(row.get("wallet")) for row in sample}
    valid_candidates = [
        row for row in registry
        if row.get("status") not in {"EXCLUDED", "INACTIVE"}
        and bool(row.get("data_complete"))
        and not any(bool(row.get(flag)) for flag in FLAGS)
    ]
    elapsed_ready = 0
    observation_ready = 0
    for row in valid_candidates:
        eligible_after = _parse_time(row.get("eligible_after"))
        if eligible_after and as_of >= eligible_after:
            elapsed_ready += 1
        if int(row.get("successful_observation_days") or 0) >= minimum_days:
            observation_ready += 1
    profiles = Counter(str(row.get("symbol_profile") or "unknown") for row in registry)
    days = Counter(int(row.get("successful_observation_days") or 0) for row in registry)
    structural_ok = (
        len(registry) == 100
        and len(pool) == 200
        and len(wallets) == len(set(wallets))
        and len(sample) == len(sample_wallets)
        and active_wallets == sample_wallets
    )
    promotion_ready = bool(
        structural_ok
        and valid_candidates
        and len(active_wallets) == len(valid_candidates)
        and elapsed_ready == len(valid_candidates)
        and observation_ready == len(valid_candidates)
    )
    return {
        "cohort_id": path.name,
        "registry_wallets": len(registry),
        "pool_wallets": len(pool),
        "sample_wallets": len(sample),
        "duplicates": len(wallets) - len(set(wallets)),
        "sample_duplicates": len(sample) - len(sample_wallets),
        "complete_histories": sum(bool(row.get("data_complete")) for row in registry),
        "incomplete_histories": sum(not bool(row.get("data_complete")) for row in registry),
        "status_counts": dict(sorted(Counter(str(row.get("status")) for row in registry).items())),
        "successful_observation_days": {str(key): value for key, value in sorted(days.items())},
        "bot_suspected": sum(bool(row.get("bot_suspected")) for row in registry),
        "mm_suspected": sum(bool(row.get("mm_suspected")) for row in registry),
        "farm_suspected": sum(bool(row.get("farm_suspected")) for row in registry),
        "arbitrage_suspected": sum(bool(row.get("arbitrage_suspected")) for row in registry),
        "small_alt_core": profiles.get("small_alt_core", 0),
        "valid_candidates": len(valid_candidates),
        "elapsed_ready_candidates": elapsed_ready,
        "observation_ready_candidates": observation_ready,
        "active_wallets": len(active_wallets),
        "active_sample_mismatch": len(active_wallets ^ sample_wallets),
        "structural_gate": "PASS" if structural_ok else "FAIL",
        "promotion_gate": "READY_FOR_HUMAN_REVIEW" if promotion_ready else "HOLD",
    }


def build_comparison(current_path: Path, shadow_path: Path, as_of: datetime,
                     minimum_days: int = 7) -> dict:
    current = summarize_cohort(current_path, as_of, minimum_days)
    shadow = summarize_cohort(shadow_path, as_of, minimum_days)
    delta_fields = ("complete_histories", "incomplete_histories", "bot_suspected",
                    "mm_suspected", "farm_suspected", "small_alt_core", "valid_candidates")
    return {
        "schema_version": 1,
        "generated_at": as_of.isoformat(),
        "minimum_successful_jst_observation_days": minimum_days,
        "decision_policy": "report only; never replace, merge, promote, trade, or notify automatically",
        "current": current,
        "shadow": shadow,
        "shadow_minus_current": {field: shadow[field] - current[field] for field in delta_fields},
        "replacement_gate": (
            "READY_FOR_HUMAN_REVIEW"
            if current["promotion_gate"] == shadow["promotion_gate"] == "READY_FOR_HUMAN_REVIEW"
            else "HOLD"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare isolated Hoihoi cohorts without mutating them")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--minimum-days", type=int, default=7)
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    report = build_comparison(args.current, args.shadow, as_of, args.minimum_days)
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
