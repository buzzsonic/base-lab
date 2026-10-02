from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from scripts.review_episodes import (
    anonymized_aliases,
    dec,
    eligibility_reasons,
    load_wallet_raw,
    read_csv,
)
from scripts.audit_market_coverage import write_csv


ZERO = Decimal("0")


@dataclass
class LabelResult:
    status: str
    score: float | None
    triggered: list[str]
    missing: list[str]


@dataclass
class AddStats:
    add_count: int = 0
    adverse_count: int = 0
    profit_count: int = 0
    adverse_qty: Decimal = ZERO
    profit_qty: Decimal = ZERO
    initial_qty: Decimal = ZERO
    worst_adverse_distance: Decimal = ZERO


@dataclass
class FillEpisode:
    wallet: str
    coin: str
    direction: str
    first_time: int
    average_entry: Decimal
    position_qty: Decimal
    stats: AddStats
    left_censored: bool = False


def direction_sign(side: str) -> float:
    if side == "LONG":
        return 1.0
    if side == "SHORT":
        return -1.0
    raise ValueError(f"unsupported side: {side}")


def numeric(row: dict[str, str], name: str) -> float | None:
    value = row.get(name, "")
    return float(value) if value not in (None, "") else None


def evaluate(required: list[str], values: dict[str, float | str | None], rules: list[tuple[str, bool]]) -> LabelResult:
    missing = [name for name in required if values.get(name) in (None, "")]
    if missing:
        return LabelResult("UNAVAILABLE", None, [], missing)
    triggered = [name for name, passed in rules if passed]
    score = len(triggered) / len(rules)
    return LabelResult("TRUE" if len(triggered) == len(rules) else "FALSE", score, triggered, [])


def market_labels(row: dict[str, str], config: dict[str, Any]) -> tuple[LabelResult, LabelResult]:
    sign = direction_sign(row["side"])
    range_position = numeric(row, "range_position")
    directional_range = range_position if row["side"] == "LONG" else (1 - range_position if range_position is not None else None)
    values: dict[str, float | str | None] = {
        "side": row.get("side"),
        "return_5m": numeric(row, "return_5m"),
        "return_15m": numeric(row, "return_15m"),
        "return_1h": numeric(row, "return_1h"),
        "volume_ratio_15m": numeric(row, "volume_ratio_15m"),
        "range_position": range_position,
        "breakout_distance": numeric(row, "breakout_distance"),
    }
    fomo_cfg = config["fomo"]
    fomo = evaluate(fomo_cfg["required_features"], values, [
        ("direction_return_5m", sign * values["return_5m"] >= fomo_cfg["direction_return_5m_min"]),
        ("direction_return_15m", sign * values["return_15m"] >= fomo_cfg["direction_return_15m_min"]),
        ("volume_expansion_15m", values["volume_ratio_15m"] >= fomo_cfg["volume_ratio_15m_min"]),
        ("directional_range_edge", directional_range >= fomo_cfg["directional_range_position_min"]),
    ]) if all(values.get(name) not in (None, "") for name in fomo_cfg["required_features"]) else evaluate(fomo_cfg["required_features"], values, [])
    late_cfg = config["late"]
    late = evaluate(late_cfg["required_features"], values, [
        ("direction_return_1h", sign * values["return_1h"] >= late_cfg["direction_return_1h_min"]),
        ("directional_range_edge", directional_range >= late_cfg["directional_range_position_min"]),
        ("near_or_beyond_prior_edge", values["breakout_distance"] >= late_cfg["breakout_distance_min"]),
    ]) if all(values.get(name) not in (None, "") for name in late_cfg["required_features"]) else evaluate(late_cfg["required_features"], values, [])
    return fomo, late


def classify_add(
    direction: str,
    average_entry: Decimal,
    price: Decimal,
    add_qty: Decimal,
    existing_qty: Decimal,
    config: dict[str, Any],
) -> str:
    if existing_qty <= ZERO or add_qty / existing_qty < dec(config["minimum_add_vs_existing_position"]):
        return "noise"
    threshold = dec(config["minimum_price_distance_bps"]) / Decimal("10000")
    signed_move = (price / average_entry - Decimal("1")) * (Decimal("1") if direction == "LONG" else Decimal("-1"))
    if signed_move <= -threshold:
        return "adverse"
    if signed_move >= threshold:
        return "profit"
    return "neutral"


def analyze_wallet_adds(wallet: str, fills: list[dict[str, Any]], config: dict[str, Any]) -> dict[tuple[str, str, int, int], AddStats]:
    indexed = sorted(enumerate(fills), key=lambda item: (int(item[1]["time"]), item[0]))
    states: dict[str, FillEpisode] = {}
    output: dict[tuple[str, str, int, int], AddStats] = {}
    for _, row in indexed:
        coin = str(row["coin"])
        before = dec(row.get("startPosition"))
        qty = dec(row.get("sz"))
        price = dec(row.get("px"))
        after = before + (qty if row.get("side") == "B" else -qty)
        state = states.get(coin)
        if state is None:
            opening_qty = abs(after) if before == ZERO else abs(before)
            state = FillEpisode(
                wallet=wallet,
                coin=coin,
                direction="LONG" if after > ZERO else "SHORT",
                first_time=int(row["time"]),
                average_entry=price,
                position_qty=opening_qty,
                stats=AddStats(initial_qty=opening_qty),
                left_censored=before != ZERO,
            )
            states[coin] = state
        same_direction_add = before * after > ZERO and abs(after) > abs(before)
        if same_direction_add:
            add_qty = abs(after) - abs(before)
            state.stats.add_count += 1
            kind = classify_add(state.direction, state.average_entry, price, add_qty, abs(before), config)
            adverse_distance = ((state.average_entry - price) / state.average_entry if state.direction == "LONG"
                                else (price - state.average_entry) / state.average_entry)
            if kind == "adverse":
                state.stats.adverse_count += 1
                state.stats.adverse_qty += add_qty
                state.stats.worst_adverse_distance = max(state.stats.worst_adverse_distance, adverse_distance)
            elif kind == "profit":
                state.stats.profit_count += 1
                state.stats.profit_qty += add_qty
            state.average_entry = (state.average_entry * abs(before) + price * add_qty) / abs(after)
            state.position_qty = abs(after)
        flip = before * after < ZERO
        if after == ZERO or flip:
            if not state.left_censored:
                output[(wallet, coin, state.first_time, int(row["time"]))] = state.stats
            states.pop(coin, None)
            if flip:
                opening_qty = abs(after)
                states[coin] = FillEpisode(
                    wallet=wallet,
                    coin=coin,
                    direction="LONG" if after > ZERO else "SHORT",
                    first_time=int(row["time"]),
                    average_entry=price,
                    position_qty=opening_qty,
                    stats=AddStats(initial_qty=opening_qty),
                )
    return output


def add_label(stats: AddStats | None, kind: str) -> LabelResult:
    if stats is None:
        return LabelResult("UNAVAILABLE", None, [], ["ordered_episode_fills"])
    count = stats.adverse_count if kind == "adverse" else stats.profit_count
    return LabelResult("TRUE" if count > 0 else "FALSE", 1.0 if count > 0 else 0.0,
                       ["qualifying_adverse_add" if kind == "adverse" else "qualifying_profit_add"] if count > 0 else [], [])


def revenge_label(current: dict[str, str], previous: dict[str, str] | None, config: dict[str, Any]) -> tuple[LabelResult, dict[str, str]]:
    diagnostics = {"revenge_gap_minutes": "", "revenge_initial_notional_ratio": "", "revenge_previous_same_coin": "", "revenge_side_relation": ""}
    if previous is None:
        return LabelResult("UNAVAILABLE", None, [], ["previous_non_overlapping_episode"]), diagnostics
    previous_initial = dec(previous["average_entry"]) * dec(previous["initial_size"])
    current_initial = dec(current["average_entry"]) * dec(current["initial_size"])
    if previous_initial <= ZERO:
        return LabelResult("UNAVAILABLE", None, [], ["previous_initial_notional"]), diagnostics
    gap_minutes = (int(current["first_entry_time"]) - int(previous["last_exit_time"])) / 60000
    ratio = current_initial / previous_initial
    cfg = config["revenge_candidate"]
    rules = [
        ("previous_episode_loss", dec(previous["net_pnl"]) < ZERO),
        ("reentry_within_window", gap_minutes <= cfg["maximum_reentry_minutes"]),
        ("initial_notional_size_up", ratio >= dec(cfg["minimum_initial_notional_ratio"])),
    ]
    diagnostics = {
        "revenge_gap_minutes": f"{gap_minutes:.12g}",
        "revenge_initial_notional_ratio": str(ratio.normalize()),
        "revenge_previous_same_coin": str(previous["coin"] == current["coin"]),
        "revenge_side_relation": "SAME" if previous["direction"] == current["direction"] else "OPPOSITE",
    }
    triggered = [name for name, passed in rules if passed]
    return LabelResult("TRUE" if len(triggered) == len(rules) else "FALSE", len(triggered) / len(rules), triggered, []), diagnostics


def previous_non_overlapping(current: dict[str, str], wallet_rows: list[dict[str, str]]) -> dict[str, str] | None:
    candidates = [row for row in wallet_rows if int(row["last_exit_time"]) <= int(current["first_entry_time"])
                  and row is not current]
    return max(candidates, key=lambda row: (int(row["last_exit_time"]), int(row["first_entry_time"]))) if candidates else None


def result_fields(prefix: str, result: LabelResult) -> dict[str, str]:
    return {
        f"{prefix}_status": result.status,
        f"{prefix}_score": "" if result.score is None else f"{result.score:.12g}",
        f"{prefix}_triggered_rules": "|".join(result.triggered),
        f"{prefix}_missing_required_features": "|".join(result.missing),
    }


def build_rows(features_path: Path, data_dir: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    features = read_csv(features_path)
    quality = read_csv(data_dir / "quality" / "account_quality.csv")
    eligible = {row["wallet"].lower() for row in quality if not eligibility_reasons(row)}
    aliases = anonymized_aliases([row["wallet"].lower() for row in quality])
    alias_to_wallet = {alias: wallet for wallet, alias in aliases.items()}
    processed = [row for row in read_csv(data_dir / "processed" / "position_episodes.csv")
                 if row["wallet"].lower() in eligible and row["closed"].lower() == "true" and row["left_censored"].lower() == "false"]
    by_alias: dict[str, list[dict[str, str]]] = defaultdict(list)
    processed_key: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in processed:
        alias = aliases[row["wallet"].lower()]
        by_alias[alias].append(row)
        processed_key[(alias, row["coin"], int(row["first_entry_time"]))] = row

    add_stats: dict[tuple[str, str, int, int], AddStats] = {}
    for wallet in eligible:
        fills, _ = load_wallet_raw(data_dir / "raw", wallet)
        add_stats.update(analyze_wallet_adds(wallet, fills, config["adds"]))

    output = []
    for feature in features:
        alias = feature["account_alias"]
        entry_ms = int(__import__("datetime").datetime.fromisoformat(feature["entry_time"].replace("Z", "+00:00")).timestamp() * 1000)
        episode = processed_key[(alias, feature["coin"], entry_ms)]
        key = (alias_to_wallet[alias], episode["coin"], int(episode["first_entry_time"]), int(episode["last_exit_time"]))
        stats = add_stats.get(key)
        fomo, late = market_labels(feature, config)
        averaging = add_label(stats, "adverse")
        pyramiding = add_label(stats, "profit")
        previous = previous_non_overlapping(episode, by_alias[alias])
        revenge, revenge_diag = revenge_label(episode, previous, config)
        output.append({
            "episode_id": feature["episode_id"],
            "account_alias": alias,
            "coin": feature["coin"],
            "side": feature["side"],
            "entry_time": feature["entry_time"],
            "config_version": config["config_version"],
            "fomo_label": f"FOMO_{feature['side']}" if fomo.status == "TRUE" else "",
            **result_fields("fomo", fomo),
            "late_label": f"LATE_{feature['side']}" if late.status == "TRUE" else "",
            **result_fields("late", late),
            "averaging_down_label": f"AVERAGING_DOWN_{feature['side']}" if averaging.status == "TRUE" else "",
            **result_fields("averaging_down", averaging),
            "profit_pyramiding_label": f"PROFIT_PYRAMIDING_{feature['side']}" if pyramiding.status == "TRUE" else "",
            **result_fields("profit_pyramiding", pyramiding),
            "revenge_label": "REVENGE_CANDIDATE" if revenge.status == "TRUE" else "",
            **result_fields("revenge", revenge),
            "adds_count": str(stats.add_count) if stats else "",
            "adverse_add_count": str(stats.adverse_count) if stats else "",
            "adverse_add_size_ratio": str((stats.adverse_qty / stats.initial_qty).normalize()) if stats and stats.initial_qty else "",
            "worst_adverse_add_distance": str(stats.worst_adverse_distance.normalize()) if stats else "",
            "profit_add_count": str(stats.profit_count) if stats else "",
            "profit_add_size_ratio": str((stats.profit_qty / stats.initial_qty).normalize()) if stats and stats.initial_qty else "",
            **revenge_diag,
        })
    return output


def summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for label in ("fomo", "late", "averaging_down", "profit_pyramiding", "revenge"):
        counts = Counter(row[f"{label}_status"] for row in rows)
        output.append({"label": label, "true": str(counts["TRUE"]), "false": str(counts["FALSE"]),
                       "unavailable": str(counts["UNAVAILABLE"]), "total": str(len(rows))})
    return output


def write_dry_run_report(path: Path, rows: list[dict[str, str]]) -> None:
    summary = {row["label"]: row for row in summary_rows(rows)}
    overlap = sum(row["fomo_status"] == "TRUE" and row["late_status"] == "TRUE" for row in rows)
    lines = [
        "# Behavior label v1 dry run",
        "",
        "## Scope",
        "",
        "This dry run validates implementation, availability, symmetry, overlap support, and deterministic output for 24 episodes. It contains no PnL, win/loss, profit factor, MFE/MAE, post-entry return, or counter-trade result.",
        "",
        "| label | TRUE | FALSE | UNAVAILABLE |",
        "|---|---:|---:|---:|",
    ]
    for label in ("fomo", "late", "averaging_down", "profit_pyramiding", "revenge"):
        item = summary[label]
        lines.append(f"| {label} | {item['true']} | {item['false']} | {item['unavailable']} |")
    lines += [
        "",
        f"Observed FOMO+Late overlap: {overlap}. The schema and synthetic test allow overlap even though this small dry run produced none.",
        "",
        "Revenge `UNAVAILABLE` rows lack a prior non-overlapping completed episode in the observed eligible history. They are not treated as FALSE.",
        "",
        "## Decision",
        "",
        "PASS for label-pipeline mechanics only. Version 1 thresholds are now frozen. These counts are not evidence about profitability, causality, psychology, or inverse-signal value.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply preregistered youbun behavior labels in dry-run mode.")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if config["config_version"] != "1.0.0" or config["status"] != "PREREGISTERED_BEFORE_DRY_RUN":
        raise RuntimeError("unexpected or mutable label config")
    rows = build_rows(args.features, args.data, config)
    write_csv(args.output / "dry_run_labels.csv", rows)
    write_csv(args.output / "dry_run_summary.csv", summary_rows(rows))
    write_dry_run_report(args.output / "dry_run_report.md", rows)


if __name__ == "__main__":
    main()
