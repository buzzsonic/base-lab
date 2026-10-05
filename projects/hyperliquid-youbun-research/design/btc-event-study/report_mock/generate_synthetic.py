#!/usr/bin/env python3
"""Generate deterministic, explicitly synthetic rows for the PHASE 2 report mock."""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SEED = 20261005
HORIZONS = (5, 15, 30, 60)

SCENARIOS = (
    {
        "scenario": "BASELINE",
        "label": "通常window",
        "count": 48,
        "imbalance": 0.05,
        "entry_concentration": 0.34,
        "oi_change": 0.0005,
        "break_failure": False,
        "opposite_flow_probability": 0.18,
        "return_bias": 0.0,
    },
    {
        "scenario": "LONG_CROWD_HIGH_FAIL",
        "label": "LONG集中・高値近辺・高値更新失敗",
        "count": 24,
        "imbalance": 0.78,
        "entry_concentration": 0.76,
        "oi_change": 0.018,
        "break_failure": True,
        "opposite_flow_probability": 0.67,
        "return_bias": -0.0025,
    },
    {
        "scenario": "SHORT_CROWD_LOW_FAIL",
        "label": "SHORT集中・安値近辺・安値更新失敗",
        "count": 20,
        "imbalance": -0.74,
        "entry_concentration": 0.71,
        "oi_change": 0.014,
        "break_failure": True,
        "opposite_flow_probability": 0.60,
        "return_bias": 0.0022,
    },
    {
        "scenario": "LONG_CROWD_OI_UP",
        "label": "LONG集中・OI増加",
        "count": 20,
        "imbalance": 0.68,
        "entry_concentration": 0.58,
        "oi_change": 0.022,
        "break_failure": False,
        "opposite_flow_probability": 0.42,
        "return_bias": -0.0008,
    },
    {
        "scenario": "OPTIONAL_COVERAGE_MISSING",
        "label": "optional coverage不足",
        "count": 8,
        "imbalance": 0.61,
        "entry_concentration": 0.63,
        "oi_change": 0.011,
        "break_failure": False,
        "opposite_flow_probability": None,
        "return_bias": 0.0,
    },
)


EVENT_FIELDS = [
    "event_id",
    "scenario",
    "scenario_label",
    "cutoff_ms",
    "active_youbun_wallets",
    "new_long_wallets",
    "new_short_wallets",
    "long_notional_usd",
    "short_notional_usd",
    "long_short_imbalance",
    "entry_price_concentration_25bps",
    "entry_distance_from_prior_60m_high_bps",
    "entry_distance_from_prior_60m_low_bps",
    "averaging_down_wallets",
    "pyramiding_wallets",
    "realized_loss_exit_wallets",
    "leverage_median",
    "liquidation_distance_bps_median",
    "btc_return_prior_60m",
    "btc_oi_change_pct",
    "btc_high_break_failed",
    "btc_low_break_failed",
    "wallet_state_coverage",
    "trade_outcome_available",
    "feature_ready",
]

OUTCOME_FIELDS = [
    "event_id",
    "scenario",
    "scenario_label",
    "horizon_min",
    "future_return",
    "mfe_up",
    "mae_down",
    "moved_against_crowd",
    "opposite_large_flow_occurred",
    "panic_exit_candidate_wallets",
    "explicit_liquidation_wallets",
    "price_outcome_status",
    "trade_outcome_status",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build() -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    events: list[dict] = []
    outcomes: list[dict] = []
    base_ms = 1791158400000
    sequence = 0

    for config in SCENARIOS:
        for _ in range(config["count"]):
            sequence += 1
            event_id = f"SYN-{sequence:04d}"
            imbalance = clamp(config["imbalance"] + rng.gauss(0, 0.09), -0.95, 0.95)
            active = rng.randint(7, 32)
            directional_share = (imbalance + 1) / 2
            new_long = max(0, round(active * directional_share * rng.uniform(0.35, 0.75)))
            new_short = max(0, round(active * (1 - directional_share) * rng.uniform(0.35, 0.75)))
            gross = rng.uniform(0.6, 4.8) * 1_000_000
            long_notional = gross * directional_share
            short_notional = gross - long_notional
            optional_missing = config["scenario"] == "OPTIONAL_COVERAGE_MISSING"
            crowd_long = imbalance > 0
            event = {
                "event_id": event_id,
                "scenario": config["scenario"],
                "scenario_label": config["label"],
                "cutoff_ms": base_ms + sequence * 300_000,
                "active_youbun_wallets": active,
                "new_long_wallets": new_long,
                "new_short_wallets": new_short,
                "long_notional_usd": round(long_notional, 2),
                "short_notional_usd": round(short_notional, 2),
                "long_short_imbalance": round(imbalance, 6),
                "entry_price_concentration_25bps": round(clamp(config["entry_concentration"] + rng.gauss(0, 0.07), 0.05, 0.95), 6),
                "entry_distance_from_prior_60m_high_bps": round(rng.uniform(-18, 4) if crowd_long else rng.uniform(-90, -25), 3),
                "entry_distance_from_prior_60m_low_bps": round(rng.uniform(25, 90) if crowd_long else rng.uniform(-4, 18), 3),
                "averaging_down_wallets": rng.randint(0, 6),
                "pyramiding_wallets": rng.randint(0, 6),
                "realized_loss_exit_wallets": rng.randint(0, 4),
                "leverage_median": "" if optional_missing else round(rng.uniform(3, 14), 3),
                "liquidation_distance_bps_median": "" if optional_missing else round(rng.uniform(160, 1200), 3),
                "btc_return_prior_60m": round((0.012 if crowd_long else -0.010) + rng.gauss(0, 0.007), 6),
                "btc_oi_change_pct": round(config["oi_change"] + rng.gauss(0, 0.004), 6),
                "btc_high_break_failed": str(bool(config["break_failure"] and crowd_long)).lower(),
                "btc_low_break_failed": str(bool(config["break_failure"] and not crowd_long)).lower(),
                "wallet_state_coverage": round(rng.uniform(0.45, 0.72) if optional_missing else rng.uniform(0.82, 1.0), 6),
                "trade_outcome_available": str(not optional_missing).lower(),
                "feature_ready": "true",
            }
            events.append(event)

            for horizon in HORIZONS:
                scale = math.sqrt(horizon / 5)
                market_return = config["return_bias"] * scale + rng.gauss(0, 0.0025 * scale)
                mfe = max(0.0001, market_return + abs(rng.gauss(0.0020 * scale, 0.0012)))
                mae = min(-0.0001, market_return - abs(rng.gauss(0.0020 * scale, 0.0012)))
                crowd_aligned = market_return if crowd_long else -market_return
                flow_probability = config["opposite_flow_probability"]
                opposite_flow = "" if flow_probability is None else str(rng.random() < flow_probability).lower()
                panic_base = 3 if config["break_failure"] else 1
                outcomes.append(
                    {
                        "event_id": event_id,
                        "scenario": config["scenario"],
                        "scenario_label": config["label"],
                        "horizon_min": horizon,
                        "future_return": round(market_return, 6),
                        "mfe_up": round(mfe, 6),
                        "mae_down": round(mae, 6),
                        "moved_against_crowd": str(crowd_aligned < 0).lower(),
                        "opposite_large_flow_occurred": opposite_flow,
                        "panic_exit_candidate_wallets": rng.randint(0, panic_base + horizon // 15),
                        "explicit_liquidation_wallets": rng.randint(0, 1 if config["break_failure"] and horizon >= 30 else 0),
                        "price_outcome_status": "READY",
                        "trade_outcome_status": "UNAVAILABLE" if optional_missing else "READY",
                    }
                )
    return events, outcomes


def summarize(events: list[dict], outcomes: list[dict]) -> dict:
    summary = {
        "synthetic": True,
        "seed": SEED,
        "event_rows": len(events),
        "outcome_rows": len(outcomes),
        "horizons": list(HORIZONS),
        "scenarios": [],
    }
    for config in SCENARIOS:
        event_subset = [row for row in events if row["scenario"] == config["scenario"]]
        outcome_subset = [row for row in outcomes if row["scenario"] == config["scenario"]]
        h30 = [row for row in outcome_subset if row["horizon_min"] == 30]
        available_flow = [row for row in h30 if row["opposite_large_flow_occurred"] != ""]
        summary["scenarios"].append(
            {
                "scenario": config["scenario"],
                "label": config["label"],
                "events": len(event_subset),
                "median_imbalance": round(sorted(row["long_short_imbalance"] for row in event_subset)[len(event_subset) // 2], 6),
                "mean_return_30m": round(sum(row["future_return"] for row in h30) / len(h30), 6),
                "against_crowd_rate_30m": round(sum(row["moved_against_crowd"] == "true" for row in h30) / len(h30), 6),
                "opposite_flow_rate_30m": None if not available_flow else round(sum(row["opposite_large_flow_occurred"] == "true" for row in available_flow) / len(available_flow), 6),
                "trade_coverage_30m": round(len(available_flow) / len(h30), 6),
            }
        )
    return summary


def main() -> None:
    events, outcomes = build()
    write_csv(ROOT / "synthetic_events.csv", EVENT_FIELDS, events)
    write_csv(ROOT / "synthetic_outcomes.csv", OUTCOME_FIELDS, outcomes)
    (ROOT / "synthetic_summary.json").write_text(
        json.dumps(summarize(events, outcomes), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
