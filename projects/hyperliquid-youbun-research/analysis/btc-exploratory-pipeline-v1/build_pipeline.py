#!/usr/bin/env python3
"""Build outcome-blind BTC event features and physically separate price outcomes.

This is a pipeline-validation artifact. It reads the historical source only to
select rows before the frozen exploratory end and never reports hypothesis
performance or selects thresholds from outcomes.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import hashlib
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import median


FIVE_MIN_MS = 300_000
EXPLORATORY_END_MS = int(dt.datetime(2026, 9, 20, 23, 0, tzinfo=dt.timezone(dt.timedelta(hours=9))).timestamp() * 1000)
EVENT_SCHEMA = "btc-exploratory-event-v0.1.0"
OUTCOME_SCHEMA = "btc-exploratory-outcome-v0.1.0"
SAMPLE_VERSION = "pilot-100-corrected-eligible-44"
ZERO = Decimal("0")
MIN_ADD_RATIO = Decimal("0.05")
MIN_ADD_DISTANCE = Decimal("0.0005")
BASELINE_LENGTH = 20


def dec(value) -> Decimal:
    return Decimal(str(value or 0))


def floor_5m(timestamp_ms: int) -> int:
    return timestamp_ms // FIVE_MIN_MS * FIVE_MIN_MS


def ceil_5m(timestamp_ms: int) -> int:
    return ((timestamp_ms + FIVE_MIN_MS - 1) // FIVE_MIN_MS) * FIVE_MIN_MS


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty output: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wallet_from_filename(path: Path) -> str:
    start = path.name.index("0x")
    return path.name[start : start + 42].lower()


def source_bounds(raw_dir: Path) -> tuple[int, int]:
    bounds = set()
    for path in raw_dir.glob("fills_*.json"):
        parts = path.stem.rsplit("_", 2)
        bounds.add((int(parts[-2]), int(parts[-1])))
    if len(bounds) != 1:
        raise ValueError(f"expected one fixed source interval, found {len(bounds)}")
    return next(iter(bounds))


def after_position(fill: dict) -> Decimal:
    before = dec(fill["startPosition"])
    size = dec(fill["sz"])
    return before + (size if fill["side"] == "B" else -size)


def order_position_chain(rows: list[dict], tolerance: Decimal = Decimal("0.00000001")) -> list[dict]:
    """Order same-timestamp rows using the observed startPosition chain."""
    by_time: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_time[int(row["time"])].append((index, row))
    ordered = []
    expected = None
    for timestamp in sorted(by_time):
        remaining = list(by_time[timestamp])
        while remaining:
            matches = [item for item in remaining if expected is not None and abs(dec(item[1]["startPosition"]) - expected) <= tolerance]
            if matches:
                chosen = min(matches, key=lambda item: item[0])
            elif expected is None:
                afters = [after_position(row) for _, row in remaining]
                heads = [item for item in remaining if not any(abs(dec(item[1]["startPosition"]) - value) <= tolerance for value in afters)]
                chosen = min(heads or remaining, key=lambda item: item[0])
            else:
                chosen = min(remaining, key=lambda item: item[0])
            remaining.remove(chosen)
            expected = after_position(chosen[1])
            ordered.append(chosen[1])
    return ordered


def load_eligible(repo_root: Path) -> set[str]:
    sampling = read_csv(repo_root / "sampling/pilot-100-v1/sampling_manifest.csv")
    audit = {row["anon_wallet_id"]: row for row in read_csv(repo_root / "reviews/pilot-100-reconstruction-audit-2026-10-03/wallet_audit.csv")}
    eligible = {
        row["wallet"].lower()
        for row in sampling
        if audit[row["anon_wallet_id"]]["eligible"] == "True"
        and audit[row["anon_wallet_id"]]["same_fixed_window_coverage"] == "True"
        and audit[row["anon_wallet_id"]]["continuity_errors"] == "0"
        and audit[row["anon_wallet_id"]]["quantity_mismatches"] == "0"
    }
    if len(eligible) != 44:
        raise ValueError(f"eligible wallet contract changed: {len(eligible)}")
    return eligible


def load_btc_fills(raw_dir: Path, eligible: set[str], end_ms: int) -> dict[str, list[dict]]:
    per_wallet: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    for source, pattern in (("regular", "fills_*.json"), ("twap", "twap_fills_*.json")):
        for filename in sorted(glob.glob(str(raw_dir / pattern))):
            path = Path(filename)
            wallet = wallet_from_filename(path)
            if wallet not in eligible:
                continue
            for row in json.loads(path.read_text(encoding="utf-8")):
                if row.get("coin") != "BTC" or int(row["time"]) >= end_ms:
                    continue
                key = row.get("tid") or (row.get("hash"), row.get("oid"), row.get("time"), row.get("px"), row.get("sz"))
                if key in seen[wallet]:
                    continue
                seen[wallet].add(key)
                per_wallet[wallet].append({**row, "source_kind": source})
    return {wallet: order_position_chain(rows) for wallet, rows in per_wallet.items()}


def canonical_input_sha256(per_wallet: dict[str, list[dict]]) -> str:
    """Hash exploratory BTC inputs without publishing wallet identifiers."""
    wallet_digests = []
    for rows in per_wallet.values():
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        wallet_digests.append(hashlib.sha256(payload).hexdigest())
    return hashlib.sha256("\n".join(sorted(wallet_digests)).encode()).hexdigest()


@dataclass
class PositionState:
    side: str
    average_entry: Decimal | None


def quantile(values: list[Decimal], probability: Decimal) -> Decimal:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    location = probability * Decimal(len(ordered) - 1)
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    weight = location - lower
    return ordered[lower] * (Decimal(1) - weight) + ordered[upper] * weight


def classify_add(side: str, average_entry: Decimal | None, price: Decimal, add_size: Decimal, before_size: Decimal) -> str:
    if average_entry is None or before_size <= ZERO:
        return "UNAVAILABLE"
    if add_size / before_size < MIN_ADD_RATIO:
        return "NOISE"
    signed_move = (price / average_entry - Decimal(1)) * (Decimal(1) if side == "LONG" else Decimal(-1))
    if signed_move <= -MIN_ADD_DISTANCE:
        return "ADVERSE"
    if signed_move >= MIN_ADD_DISTANCE:
        return "FAVORABLE"
    return "NEUTRAL"


def blank_bucket(window_start_ms: int, cutoff_ms: int, eligible_count: int) -> dict:
    return {
        "schema_version": EVENT_SCHEMA,
        "sample_version": SAMPLE_VERSION,
        "split": "exploratory",
        "window_start_ms": window_start_ms,
        "cutoff_ms": cutoff_ms,
        "eligible_wallets": eligible_count,
        "wallet_flow_status": "READY",
        "wallet_activity_status": "ZERO_ACTIVITY",
        "wallet_source_gap_count": 0,
        "active_wallets": set(),
        "new_long_wallets_set": set(),
        "new_short_wallets_set": set(),
        "add_wallets_set": set(),
        "averaging_down_wallets_set": set(),
        "pyramiding_wallets_set": set(),
        "add_state_unavailable_wallets_set": set(),
        "size_baseline_ready_wallets_set": set(),
        "long_notional": ZERO,
        "short_notional": ZERO,
        "new_long_notional": ZERO,
        "new_short_notional": ZERO,
        "add_notional": ZERO,
        "adverse_add_notional": ZERO,
        "favorable_add_notional": ZERO,
        "size_ratios": [],
        "entries": defaultdict(lambda: {"qty": ZERO, "notional": ZERO}),
    }


def add_increase(bucket: dict, wallet: str, side: str, price: Decimal, size: Decimal, transition: str) -> None:
    notional = price * size
    bucket["active_wallets"].add(wallet)
    bucket["wallet_activity_status"] = "ACTIVITY_OBSERVED"
    if side == "LONG":
        bucket["long_notional"] += notional
    else:
        bucket["short_notional"] += notional
    if transition == "NEW":
        bucket[f"new_{side.lower()}_wallets_set"].add(wallet)
        bucket[f"new_{side.lower()}_notional"] += notional
        bucket["entries"][wallet]["qty"] += size
        bucket["entries"][wallet]["notional"] += notional
    else:
        bucket["add_wallets_set"].add(wallet)
        bucket["add_notional"] += notional


def aggregate_wallet_fills(per_wallet: dict[str, list[dict]], buckets: dict[int, dict]) -> None:
    for wallet, fills in per_wallet.items():
        state: PositionState | None = None
        past_increase_notionals: deque[Decimal] = deque(maxlen=BASELINE_LENGTH)
        for row in fills:
            timestamp = int(row["time"])
            before = dec(row["startPosition"])
            after = after_position(row)
            price = dec(row["px"])
            bucket = buckets.get(floor_5m(timestamp))
            if bucket is not None:
                bucket["active_wallets"].add(wallet)
                bucket["wallet_activity_status"] = "ACTIVITY_OBSERVED"

            if state is None and before != ZERO:
                state = PositionState("LONG" if before > ZERO else "SHORT", None)

            increases: list[tuple[str, Decimal, str]] = []
            if before == ZERO and after != ZERO:
                increases.append(("LONG" if after > ZERO else "SHORT", abs(after), "NEW"))
            elif before * after < ZERO:
                increases.append(("LONG" if after > ZERO else "SHORT", abs(after), "NEW"))
            elif before * after > ZERO and abs(after) > abs(before):
                increases.append(("LONG" if after > ZERO else "SHORT", abs(after) - abs(before), "ADD"))

            for side, increase_size, transition in increases:
                notional = price * increase_size
                if bucket is not None:
                    add_increase(bucket, wallet, side, price, increase_size, transition)
                    if len(past_increase_notionals) == BASELINE_LENGTH:
                        baseline = median(past_increase_notionals)
                        if baseline > ZERO:
                            bucket["size_baseline_ready_wallets_set"].add(wallet)
                            bucket["size_ratios"].append(notional / baseline)
                past_increase_notionals.append(notional)

            same_direction_add = before * after > ZERO and abs(after) > abs(before)
            if same_direction_add:
                add_size = abs(after) - abs(before)
                side = "LONG" if after > ZERO else "SHORT"
                kind = classify_add(side, state.average_entry if state else None, price, add_size, abs(before))
                if bucket is not None:
                    notional = price * add_size
                    if kind == "ADVERSE":
                        bucket["averaging_down_wallets_set"].add(wallet)
                        bucket["adverse_add_notional"] += notional
                    elif kind == "FAVORABLE":
                        bucket["pyramiding_wallets_set"].add(wallet)
                        bucket["favorable_add_notional"] += notional
                    elif kind == "UNAVAILABLE":
                        bucket["add_state_unavailable_wallets_set"].add(wallet)
                if state and state.average_entry is not None:
                    state.average_entry = (state.average_entry * abs(before) + price * add_size) / abs(after)

            if before == ZERO and after != ZERO:
                state = PositionState("LONG" if after > ZERO else "SHORT", price)
            elif before * after < ZERO:
                state = PositionState("LONG" if after > ZERO else "SHORT", price)
            elif after == ZERO:
                state = None


def decimal_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def candle_features(window_start: int, candles: dict[int, dict]) -> dict:
    current = candles.get(window_start)
    if current is None:
        return {
            "btc_candle_status": "UNAVAILABLE", "btc_open": "", "btc_high": "", "btc_low": "", "btc_close": "",
            "btc_volume_5m": "", "btc_return_5m": "", "prior_60m_status": "UNAVAILABLE",
            "btc_return_prior_60m": "", "btc_volume_ratio_prior_60m": "", "btc_prior_60m_high": "", "btc_prior_60m_low": "",
        }
    prior_times = [window_start - offset * FIVE_MIN_MS for offset in range(11, -1, -1)]
    prior = [candles.get(timestamp) for timestamp in prior_times]
    output = {
        "btc_candle_status": "READY",
        "btc_open": current["o"], "btc_high": current["h"], "btc_low": current["l"], "btc_close": current["c"],
        "btc_volume_5m": current["v"],
        "btc_return_5m": decimal_text(dec(current["c"]) / dec(current["o"]) - Decimal(1)),
        "prior_60m_status": "READY" if all(prior) else "UNAVAILABLE",
        "btc_return_prior_60m": "", "btc_volume_ratio_prior_60m": "", "btc_prior_60m_high": "", "btc_prior_60m_low": "",
    }
    if all(prior):
        prior_volume = sum((dec(row["v"]) for row in prior[:-1]), ZERO) / Decimal(11)
        output.update({
            "btc_return_prior_60m": decimal_text(dec(prior[-1]["c"]) / dec(prior[0]["o"]) - Decimal(1)),
            "btc_volume_ratio_prior_60m": decimal_text(dec(prior[-1]["v"]) / prior_volume) if prior_volume else "",
            "btc_prior_60m_high": decimal_text(max(dec(row["h"]) for row in prior)),
            "btc_prior_60m_low": decimal_text(min(dec(row["l"]) for row in prior)),
        })
    return output


def finalize_event(bucket: dict, candles: dict[int, dict]) -> dict:
    entries = []
    for wallet_data in bucket["entries"].values():
        if wallet_data["qty"] > ZERO:
            entries.append((wallet_data["notional"] / wallet_data["qty"], wallet_data["notional"], wallet_data["qty"]))
    total_increase = bucket["long_notional"] + bucket["short_notional"]
    total_entry_notional = sum((item[1] for item in entries), ZERO)
    total_entry_qty = sum((item[2] for item in entries), ZERO)
    entry_median = median([item[0] for item in entries]) if entries else None
    iqr = None
    concentration = None
    if entries:
        prices = [item[0] for item in entries]
        iqr = (quantile(prices, Decimal("0.75")) - quantile(prices, Decimal("0.25"))) / entry_median * Decimal(10_000) if entry_median else None
        within = sum((notional for price, notional, _ in entries if abs(price / entry_median - Decimal(1)) <= Decimal("0.0025")), ZERO)
        concentration = within / total_entry_notional if total_entry_notional else None
    size_ratios = bucket["size_ratios"]
    row = {
        "schema_version": bucket["schema_version"], "sample_version": bucket["sample_version"], "split": bucket["split"],
        "window_start_ms": bucket["window_start_ms"], "cutoff_ms": bucket["cutoff_ms"], "eligible_wallets": bucket["eligible_wallets"],
        "wallet_flow_status": bucket["wallet_flow_status"], "wallet_activity_status": bucket["wallet_activity_status"],
        "wallet_source_gap_count": bucket["wallet_source_gap_count"], "active_youbun_wallets": len(bucket["active_wallets"]),
        "new_long_wallets": len(bucket["new_long_wallets_set"]), "new_short_wallets": len(bucket["new_short_wallets_set"]),
        "add_wallets": len(bucket["add_wallets_set"]), "averaging_down_wallets": len(bucket["averaging_down_wallets_set"]),
        "pyramiding_wallets": len(bucket["pyramiding_wallets_set"]), "add_state_unavailable_wallets": len(bucket["add_state_unavailable_wallets_set"]),
        "long_notional_usd": decimal_text(bucket["long_notional"]), "short_notional_usd": decimal_text(bucket["short_notional"]),
        "long_short_imbalance": decimal_text((bucket["long_notional"] - bucket["short_notional"]) / total_increase) if total_increase else "",
        "new_entry_long_notional_usd": decimal_text(bucket["new_long_notional"]), "new_entry_short_notional_usd": decimal_text(bucket["new_short_notional"]),
        "add_notional_usd": decimal_text(bucket["add_notional"]), "adverse_add_notional_usd": decimal_text(bucket["adverse_add_notional"]),
        "favorable_add_notional_usd": decimal_text(bucket["favorable_add_notional"]),
        "entry_wallets": len(entries), "entry_price_vwap": decimal_text(total_entry_notional / total_entry_qty) if total_entry_qty else "",
        "entry_price_wallet_median": decimal_text(entry_median), "entry_price_iqr_bps": decimal_text(iqr),
        "entry_price_concentration_25bps": decimal_text(concentration),
        "size_baseline_ready_wallets": len(bucket["size_baseline_ready_wallets_set"]),
        "size_increase_ratio_past20_median_median": decimal_text(median(size_ratios)) if size_ratios else "",
        "size_increase_ratio_past20_median_max": decimal_text(max(size_ratios)) if size_ratios else "",
        **candle_features(bucket["window_start_ms"], candles),
        "btc_asset_ctx_status": "UNAVAILABLE", "feature_ready": "False",
    }
    return row


def build_outcomes(events: list[dict], candles: dict[int, dict]) -> list[dict]:
    rows = []
    for event in events:
        cutoff = int(event["cutoff_ms"])
        anchor_candle = candles.get(cutoff - FIVE_MIN_MS)
        imbalance = Decimal(event["long_short_imbalance"]) if event["long_short_imbalance"] else None
        crowd_side = "LONG" if imbalance and imbalance > ZERO else ("SHORT" if imbalance and imbalance < ZERO else "")
        for horizon in (5, 15, 30, 60):
            required = [candles.get(cutoff + offset * FIVE_MIN_MS) for offset in range(horizon // 5)]
            ready = anchor_candle is not None and all(required)
            row = {
                "schema_version": OUTCOME_SCHEMA, "sample_version": SAMPLE_VERSION, "split": "exploratory",
                "cutoff_ms": cutoff, "horizon_min": horizon, "source_interval_min": 5,
                "price_outcome_status": "READY" if ready else "UNAVAILABLE",
                "missing_reason": "" if ready else ("ANCHOR_UNAVAILABLE" if anchor_candle is None else "MISSING_CANDLE"),
                "anchor_price": "", "horizon_close": "", "future_return": "", "future_up": "", "future_down": "",
                "mfe_up": "", "mae_down": "", "max_abs_move": "", "time_to_high_sec_resolution_5m": "", "time_to_low_sec_resolution_5m": "",
                "crowd_side": crowd_side, "crowd_aligned_return": "", "opposite_return": "", "moved_against_crowd": "",
            }
            if ready:
                anchor = dec(anchor_candle["c"])
                close = dec(required[-1]["c"])
                future_return = close / anchor - Decimal(1)
                max_high = max(dec(item["h"]) for item in required)
                min_low = min(dec(item["l"]) for item in required)
                mfe = max_high / anchor - Decimal(1)
                mae = min_low / anchor - Decimal(1)
                high_index = next(i for i, item in enumerate(required) if dec(item["h"]) == max_high)
                low_index = next(i for i, item in enumerate(required) if dec(item["l"]) == min_low)
                aligned = future_return if crowd_side == "LONG" else (-future_return if crowd_side == "SHORT" else None)
                row.update({
                    "anchor_price": decimal_text(anchor), "horizon_close": decimal_text(close), "future_return": decimal_text(future_return),
                    "future_up": str(future_return > ZERO), "future_down": str(future_return < ZERO),
                    "mfe_up": decimal_text(mfe), "mae_down": decimal_text(mae), "max_abs_move": decimal_text(max(abs(mfe), abs(mae))),
                    "time_to_high_sec_resolution_5m": (high_index + 1) * 300, "time_to_low_sec_resolution_5m": (low_index + 1) * 300,
                    "crowd_aligned_return": decimal_text(aligned), "opposite_return": decimal_text(-aligned) if aligned is not None else "",
                    "moved_against_crowd": str(aligned < ZERO) if aligned is not None else "",
                })
            rows.append(row)
    return rows


def run(repo_root: Path, source_root: Path, market_root: Path, output_dir: Path) -> dict:
    eligible = load_eligible(repo_root)
    source_start, source_end = source_bounds(source_root / "raw")
    if source_end < EXPLORATORY_END_MS:
        raise ValueError("source does not cover frozen exploratory end")
    first_window_start = ceil_5m(source_start)
    buckets = {
        start: blank_bucket(start, start + FIVE_MIN_MS, len(eligible))
        for start in range(first_window_start, EXPLORATORY_END_MS - FIVE_MIN_MS, FIVE_MIN_MS)
    }
    per_wallet = load_btc_fills(source_root / "raw", eligible, EXPLORATORY_END_MS)
    aggregate_wallet_fills(per_wallet, buckets)
    candle_path = market_root / "candles_5m_BTC_reference.json"
    candles_all = json.loads(candle_path.read_text(encoding="utf-8"))
    candles = {int(row["t"]): row for row in candles_all if int(row["t"]) < EXPLORATORY_END_MS + 60 * 60 * 1000}
    events = [finalize_event(buckets[start], candles) for start in sorted(buckets)]
    outcomes = build_outcomes(events, candles)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "events_exploratory.csv", events)
    write_csv(output_dir / "outcomes_exploratory.csv", outcomes)
    summary = {
        "pipeline_version": "btc-exploratory-pipeline-v1",
        "decision_scope": "PIPELINE_VALIDATION_ONLY",
        "split": "exploratory",
        "validation_or_held_out_rows_processed": 0,
        "eligible_wallets": len(eligible),
        "wallets_with_btc_fills_before_exploratory_end": len(per_wallet),
        "source_start_ms": source_start,
        "exploratory_end_exclusive_ms": EXPLORATORY_END_MS,
        "event_rows": len(events),
        "zero_activity_event_rows": sum(row["wallet_activity_status"] == "ZERO_ACTIVITY" for row in events),
        "activity_event_rows": sum(row["wallet_activity_status"] == "ACTIVITY_OBSERVED" for row in events),
        "wallet_flow_ready_rows": sum(row["wallet_flow_status"] == "READY" for row in events),
        "btc_candle_ready_rows": sum(row["btc_candle_status"] == "READY" for row in events),
        "prior_60m_ready_rows": sum(row["prior_60m_status"] == "READY" for row in events),
        "core_feature_ready_rows": sum(row["feature_ready"] == "True" for row in events),
        "new_entry_rows": sum(int(row["entry_wallets"]) > 0 for row in events),
        "averaging_down_rows": sum(int(row["averaging_down_wallets"]) > 0 for row in events),
        "size_baseline_ready_rows": sum(int(row["size_baseline_ready_wallets"]) > 0 for row in events),
        "outcome_rows": len(outcomes),
        "price_outcome_ready_by_horizon": {
            str(horizon): sum(int(row["horizon_min"]) == horizon and row["price_outcome_status"] == "READY" for row in outcomes)
            for horizon in (5, 15, 30, 60)
        },
        "blocked_series": ["historical_btc_asset_context", "historical_btc_oi", "historical_btc_trades", "historical_wallet_state", "explicit_liquidation_events"],
        "hypothesis_performance_computed": False,
        "source_sha256": {
            "canonical_exploratory_btc_fills_aggregate": canonical_input_sha256(per_wallet),
            "btc_candles": sha256(candle_path),
        },
    }
    (output_dir / "pipeline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        f"""# BTC exploratory pipeline v1

## 判定

この成果物はexploratory期間だけを使った**pipeline検証**であり、仮説の成績評価ではない。validation / held-outの処理件数は0。

- continuous 5m event rows: {summary['event_rows']:,}
- activity / zero activity: {summary['activity_event_rows']:,} / {summary['zero_activity_event_rows']:,}
- BTC candle READY: {summary['btc_candle_ready_rows']:,}
- prior 60m READY: {summary['prior_60m_ready_rows']:,}
- core feature READY: {summary['core_feature_ready_rows']:,}（historical asset contextが0%のため）
- new-entry feature rows: {summary['new_entry_rows']:,}
- averaging-down feature rows: {summary['averaging_down_rows']:,}
- past-20 size baseline ready rows: {summary['size_baseline_ready_rows']:,}
- H07 price outcome READY: {summary['price_outcome_ready_by_horizon']}

`events_exploratory.csv`にfuture return / MFE / MAEを置かず、`outcomes_exploratory.csv`へ物理分離した。5分足しかないためtime-to-high/lowは5分解像度であり、PHASE 1の1分正規schemaとは区別したexploratory schemaを使う。

OI、asset context、market trades、wallet state、明示的liquidation eventは推定せずblockを維持する。effect size、勝率、p値、逆指標性、閾値採否は計算していない。
""",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--market-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.repo_root, args.source_root, args.market_root, args.output_dir)
    print(json.dumps({key: summary[key] for key in ("event_rows", "zero_activity_event_rows", "activity_event_rows", "core_feature_ready_rows", "price_outcome_ready_by_horizon")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
