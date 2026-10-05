#!/usr/bin/env python3
"""Build reviewed aggregate rows for the synthetic PHASE 2 report mock."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(rows, field):
    values = [float(row[field]) for row in rows if row[field] != ""]
    return None if not values else sum(values) / len(values)


def rate(rows, field):
    values = [row[field] for row in rows if row[field] != ""]
    return None if not values else sum(value == "true" for value in values) / len(values)


def source(files, caveat):
    return {
        "provider": "local-synthetic-files",
        "files": [{"name": name} for name in files],
        "filters": ["Deterministic seed 20261005", "Schema demonstration only"],
        "caveats": [caveat, "No row is an observed Hyperliquid event."],
        "evidenceFlow": [
            {
                "kind": "method",
                "title": "Synthetic contract check",
                "detail": "Rows were generated only to verify report structure, missingness and feature/outcome separation.",
            }
        ],
    }


def build():
    events = read_csv("synthetic_events.csv")
    outcomes = read_csv("synthetic_outcomes.csv")
    event_groups = defaultdict(list)
    outcome_groups = defaultdict(list)
    for row in events:
        event_groups[row["scenario"]].append(row)
    for row in outcomes:
        outcome_groups[(row["scenario"], int(row["horizon_min"]))].append(row)

    scenario_rows = []
    horizon_rows = []
    chain_rows = []
    for scenario, rows in event_groups.items():
        label = rows[0]["scenario_label"]
        scenario_rows.append(
            {
                "scenario": scenario,
                "scenario_label": label,
                "events": len(rows),
                "median_imbalance": statistics.median(float(row["long_short_imbalance"]) for row in rows),
                "median_entry_concentration": statistics.median(float(row["entry_price_concentration_25bps"]) for row in rows),
                "median_active_wallets": statistics.median(int(row["active_youbun_wallets"]) for row in rows),
                "wallet_state_coverage": mean(rows, "wallet_state_coverage"),
            }
        )
        for horizon in (5, 15, 30, 60):
            subset = outcome_groups[(scenario, horizon)]
            horizon_rows.append(
                {
                    "scenario": scenario,
                    "scenario_label": label,
                    "horizon_min": horizon,
                    "mean_future_return_pct": mean(subset, "future_return") * 100,
                    "against_crowd_rate_pct": rate(subset, "moved_against_crowd") * 100,
                    "mean_mfe_pct": mean(subset, "mfe_up") * 100,
                    "mean_mae_pct": mean(subset, "mae_down") * 100,
                }
            )
            chain_rows.append(
                {
                    "scenario": scenario,
                    "scenario_label": label,
                    "horizon_min": horizon,
                    "opposite_flow_rate_pct": None if rate(subset, "opposite_large_flow_occurred") is None else rate(subset, "opposite_large_flow_occurred") * 100,
                    "mean_panic_exit_wallets": mean(subset, "panic_exit_candidate_wallets"),
                    "explicit_liquidation_event_rate_pct": rate(subset, "explicit_liquidation_wallets") * 100,
                    "trade_outcome_coverage_pct": sum(row["trade_outcome_status"] == "READY" for row in subset) / len(subset) * 100,
                }
            )

    caveat = "All metrics are intentionally synthetic and must not be interpreted as performance evidence."
    return {
        "title": "養分群の集中後に何を検証するか",
        "generatedAt": "2026-10-05T09:00:00+09:00",
        "buildStatus": "creating",
        "report": {"asOf": "2026-10-05", "synthetic": True},
        "queries": {
            "scenario-distribution": {
                "id": "scenario-distribution",
                "source": source(["synthetic_events.csv", "generate_synthetic.py"], caveat),
                "rows": scenario_rows,
            },
            "horizon-outcomes": {
                "id": "horizon-outcomes",
                "source": source(["synthetic_outcomes.csv", "outcome_schema.md"], caveat),
                "rows": horizon_rows,
            },
            "event-chain": {
                "id": "event-chain",
                "source": source(["synthetic_outcomes.csv", "event_schema.md", "outcome_schema.md"], caveat),
                "rows": chain_rows,
            },
            "mock-scope": {
                "id": "mock-scope",
                "source": source(["README.md", "synthetic_summary.json"], caveat),
                "rows": [
                    {"metric": "Synthetic event windows", "value": len(events)},
                    {"metric": "Synthetic outcome rows", "value": len(outcomes)},
                    {"metric": "Horizons", "value": "5 / 15 / 30 / 60 min"},
                    {"metric": "Observed market rows", "value": 0},
                ],
            },
        },
    }


def main():
    (ROOT / "report_snapshot.json").write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
