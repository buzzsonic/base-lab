from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.audit_market_coverage import (
    FIVE_MINUTES_MS,
    ONE_HOUR_MS,
    cache_name,
    expected_entry_bars,
    floor_5m,
    iso,
    past_funding,
    post_json,
    read_csv,
    write_csv,
)


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def exact_window(rows: list[dict[str, Any]], entry_ms: int) -> list[dict[str, Any]] | None:
    expected = expected_entry_bars(entry_ms)
    expected_set = set(expected)
    selected = [row for row in rows if int(row["t"]) in expected_set]
    by_time = {int(row["t"]): row for row in selected}
    if len(selected) != len(expected) or set(by_time) != expected_set:
        return None
    return [by_time[timestamp] for timestamp in expected]


def safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator != 0 else None


def fmt(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.12g}"


def price_return(window: list[dict[str, Any]], bars: int) -> float | None:
    subset = window[-bars:]
    return safe_ratio(float(subset[-1]["c"]), float(subset[0]["o"])) - 1 if float(subset[0]["o"]) else None


def volume_ratio(window: list[dict[str, Any]], bars: int) -> float | None:
    current = sum(float(row["v"]) for row in window[-bars:])
    prior = [float(row["v"]) for row in window[:-bars]]
    if not prior:
        return None
    prior_equivalent = sum(prior) / len(prior) * bars
    return safe_ratio(current, prior_equivalent)


def volume_zscore(window: list[dict[str, Any]]) -> float | None:
    current = float(window[-1]["v"])
    prior = [float(row["v"]) for row in window[:-1]]
    mean = sum(prior) / len(prior)
    variance = sum((value - mean) ** 2 for value in prior) / len(prior)
    return (current - mean) / math.sqrt(variance) if variance > 0 else None


def realized_volatility(window: list[dict[str, Any]]) -> float | None:
    closes = [float(row["c"]) for row in window]
    if any(value <= 0 for value in closes):
        return None
    returns = [math.log(right / left) for left, right in zip(closes, closes[1:])]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def local_structure(window: list[dict[str, Any]], side: str) -> dict[str, float | None]:
    close = float(window[-1]["c"])
    high = max(float(row["h"]) for row in window)
    low = min(float(row["l"]) for row in window)
    prior_high = max(float(row["h"]) for row in window[:-1])
    prior_low = min(float(row["l"]) for row in window[:-1])
    range_width = high - low
    breakout = safe_ratio(close, prior_high) - 1 if side == "LONG" and prior_high else None
    if side == "SHORT":
        breakout = safe_ratio(prior_low, close) - 1 if close else None
    return {
        "distance_from_local_high": safe_ratio(close, high) - 1 if high else None,
        "distance_from_local_low": safe_ratio(close, low) - 1 if low else None,
        "range_position": (close - low) / range_width if range_width else None,
        "breakout_distance": breakout,
    }


def compute_features(window: list[dict[str, Any]], side: str) -> dict[str, float | None]:
    result = {
        "return_5m": price_return(window, 1),
        "return_15m": price_return(window, 3),
        "return_1h": price_return(window, 12),
        "volume_ratio_5m": volume_ratio(window, 1),
        "volume_ratio_15m": volume_ratio(window, 3),
        "volume_zscore_1h": volume_zscore(window),
        "realized_volatility": realized_volatility(window),
    }
    result.update(local_structure(window, side))
    return result


def ensure_btc_reference(cache_dir: Path, coverage_rows: list[dict[str, str]], fetch: bool) -> Path:
    path = cache_dir / "candles_5m_BTC_reference.json"
    if path.exists():
        return path
    if not fetch:
        return path
    entries = [int(row["entry_time_ms"]) for row in coverage_rows]
    start = min(expected_entry_bars(entry)[0] for entry in entries)
    end = max(floor_5m(entry) - 1 for entry in entries)
    rows = post_json({
        "type": "candleSnapshot",
        "req": {"coin": "BTC", "interval": "5m", "startTime": start, "endTime": end},
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, separators=(",", ":")) + "\n")
    return path


def parse_iso_ms(value: str) -> int:
    from datetime import datetime
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def build_rows(coverage_path: Path, cache_dir: Path, fetch_btc: bool) -> list[dict[str, str]]:
    coverage = [row for row in read_csv(coverage_path) if row["availability_status"] == "PARTIAL"]
    if len(coverage) != 24:
        raise RuntimeError(f"expected 24 PARTIAL episodes, got {len(coverage)}")
    for row in coverage:
        row["entry_time_ms"] = str(parse_iso_ms(row["entry_time"]))
    btc_path = ensure_btc_reference(cache_dir, coverage, fetch_btc)
    btc_rows = load_json(btc_path) if btc_path.exists() else []

    output = []
    for row in coverage:
        entry_ms = int(row["entry_time_ms"])
        coin = row["coin"]
        candles = load_json(cache_dir / f"candles_5m_{cache_name(coin)}.json")
        funding_rows = load_json(cache_dir / f"funding_{cache_name(coin)}.json")
        window = exact_window(candles, entry_ms)
        if window is None:
            raise RuntimeError(f"coverage drift for {row['episode_id']}: expected complete candle window")
        features = compute_features(window, row["side"])
        btc_window = exact_window(btc_rows, entry_ms)
        btc_5m = price_return(btc_window, 1) if btc_window else None
        btc_15m = price_return(btc_window, 3) if btc_window else None
        funding = past_funding(funding_rows, entry_ms)
        funding_valid = funding is not None and entry_ms - int(funding["time"]) <= 2 * ONE_HOUR_MS
        missing = []
        if not btc_window:
            missing.append("btc_reference_window")
        if not funding_valid:
            missing.append("funding_rate")
        missing.extend(["mark", "oi"])
        output.append({
            "episode_id": row["episode_id"],
            "account_alias": row["account_alias"],
            "coin": coin,
            "side": row["side"],
            "entry_time": row["entry_time"],
            "feature_availability": "PRICE_VOLUME_BTC_FUNDING" if not missing[:-2] else "PRICE_VOLUME_BTC",
            **{name: fmt(value) for name, value in features.items()},
            "btc_return_5m": fmt(btc_5m),
            "btc_return_15m": fmt(btc_15m),
            "btc_relative_strength_5m": fmt(features["return_5m"] - btc_5m) if btc_5m is not None else "",
            "btc_relative_strength_15m": fmt(features["return_15m"] - btc_15m) if btc_15m is not None else "",
            "funding_rate": str(funding.get("fundingRate", "")) if funding_valid else "",
            "mark_price": "",
            "oi": "",
            "missing_features": ",".join(missing),
            "source_window_start": iso(expected_entry_bars(entry_ms)[0]),
            "source_window_end_exclusive": iso(floor_5m(entry_ms)),
        })
    return output


def write_definitions(path: Path) -> None:
    path.write_text("""# Past-only feature definitions

All entry features use exactly 12 completed 5-minute candles in `[floor5m(entry)-60m, floor5m(entry))`. The candle containing entry and all later candles are excluded. Prices and volumes come from the official `candleSnapshot`; Funding comes from the latest official `fundingHistory` observation at or before entry, no more than two hours old.

| feature | formula and lookback | missing rule | leakage |
|---|---|---|---|
| return_5m | last candle close / last candle open - 1 | NULL unless all 12 source bars exist | past-only |
| return_15m | last close / open three bars earlier - 1 | same | past-only |
| return_1h | last close / first open in 12-bar window - 1 | same | past-only |
| volume_ratio_5m | last-bar volume / mean volume of prior 11 bars | NULL when prior mean is zero | past-only |
| volume_ratio_15m | sum of last 3 bars / prior 9-bar mean scaled to 3 bars | NULL when prior equivalent is zero | past-only |
| volume_zscore_1h | z-score of last-bar volume against prior 11 bars, population SD | NULL when prior SD is zero | past-only |
| distance_from_local_high | last close / maximum high over 12 bars - 1 | NULL when denominator is zero | past-only |
| distance_from_local_low | last close / minimum low over 12 bars - 1 | NULL when denominator is zero | past-only |
| range_position | (last close - 12-bar low) / (12-bar high - low) | NULL for zero-width range | past-only |
| breakout_distance | LONG: last close / prior-11-bar high - 1; SHORT: prior-11-bar low / last close - 1 | NULL when denominator is zero | past-only; side-adjusted |
| realized_volatility | sample SD of 11 consecutive 5-minute log close returns | NULL for non-positive price or fewer than two returns | past-only; not annualized |
| btc_return_5m / 15m | same return definitions on BTC at the identical entry boundary | NULL unless BTC has all identical 12 timestamps | past-only |
| btc_relative_strength_5m / 15m | episode-coin return minus BTC return | NULL when BTC return is NULL | past-only |
| funding_rate | latest Funding rate with timestamp <= entry and lag <= 2h | NULL otherwise | past-only |
| mark_price / oi | not computed in this PoC | always NULL until verified historical series exists | unavailable |

No exit time, PnL, MFE, MAE, or post-entry candle participates in this file. Post-entry evaluation features are intentionally not produced in this task.
""")


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    availability = Counter(row["feature_availability"] for row in rows)
    btc = sum(bool(row["btc_return_5m"]) for row in rows)
    funding = sum(bool(row["funding_rate"]) for row in rows)
    fully_numeric = sum(not row["missing_features"].replace("mark,oi", "").strip(",") for row in rows)
    path.write_text(f"""# Past-only market features — 2026-10-02

## Result

The 24 PARTIAL episodes received deterministic price and volume features from the 12 completed 5-minute candles strictly before entry.

| check | result |
|---|---:|
| Input PARTIAL episodes | {len(rows)} |
| Price/volume feature rows | {len(rows)} |
| BTC-relative coverage | {btc}/{len(rows)} |
| Funding-rate coverage | {funding}/{len(rows)} |
| Rows with BTC and Funding available | {fully_numeric}/{len(rows)} |
| Historical mark/OI coverage | 0/{len(rows)} |
| Duplicate episode IDs | {len(rows) - len({row['episode_id'] for row in rows})} |

Availability classes: {dict(sorted(availability.items()))}.

## Gate decision

PASS for the limited price/volume feature contract. Every output row has the full 12-bar past-only source window, unavailable fields remain empty, and BTC/Funding dependencies are individually gated. This does not validate or create any behavioral label.

## Reproducibility and exclusions

- `episode_features.csv` contains only anonymized episode/account IDs; wallet addresses are absent.
- The entry candle, exit time, PnL, and all post-entry candles are physically absent from the calculation interface.
- Historical mark and OI are not inferred, interpolated, or zero-filled.
- The 37 NOT_READY episodes are not present in this feature table.
- Cached reruns must produce byte-identical CSV output.

## Artifacts

- `episode_features.csv`: 24 episode-level feature rows
- `feature_definitions.md`: formulas, lookbacks, source series, NULL rules, BTC conditions, and leakage status
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build past-only market features for PARTIAL youbun episodes.")
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fetch-btc", action="store_true")
    args = parser.parse_args()
    rows = build_rows(args.coverage, args.cache, args.fetch_btc)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "episode_features.csv", rows)
    write_definitions(args.output / "feature_definitions.md")
    write_report(args.output / "README.md", rows)


if __name__ == "__main__":
    main()
