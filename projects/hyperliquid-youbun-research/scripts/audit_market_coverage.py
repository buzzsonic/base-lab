from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.review_episodes import anonymized_aliases, eligibility_reasons, read_csv


FIVE_MINUTES_MS = 5 * 60 * 1000
ONE_HOUR_MS = 60 * 60 * 1000
API_URL = "https://api.hyperliquid.xyz/info"
USER_AGENT = "YoubunMarketCoverage/1.0"


def floor_5m(timestamp_ms: int) -> int:
    return timestamp_ms - timestamp_ms % FIVE_MINUTES_MS


def expected_entry_bars(entry_ms: int) -> list[int]:
    boundary = floor_5m(entry_ms)
    return list(range(boundary - ONE_HOUR_MS, boundary, FIVE_MINUTES_MS))


def expected_post_bars(entry_ms: int) -> list[int]:
    boundary = floor_5m(entry_ms)
    return list(range(boundary, boundary + ONE_HOUR_MS, FIVE_MINUTES_MS))


def bar_coverage(rows: list[dict[str, Any]], expected: list[int]) -> tuple[int, float]:
    available = {int(row["t"]) for row in rows if int(row["t"]) in set(expected)}
    return len(available), len(available) / len(expected) if expected else 0.0


def past_funding(rows: list[dict[str, Any]], entry_ms: int) -> dict[str, Any] | None:
    candidates = [row for row in rows if int(row["time"]) <= entry_ms]
    return max(candidates, key=lambda row: int(row["time"])) if candidates else None


def post_json(payload: dict[str, Any], retries: int = 3) -> list[dict[str, Any]]:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read())
            if not isinstance(result, list):
                raise RuntimeError(f"unexpected API response: {type(result).__name__}")
            return result
        except Exception:
            if attempt + 1 == retries:
                raise
            time.sleep(1.0 * (attempt + 1))
    raise AssertionError("unreachable")


def cache_name(coin: str) -> str:
    return coin.replace(":", "__").replace("/", "_")


def load_or_fetch(cache_path: Path, payload: dict[str, Any], refresh: bool) -> list[dict[str, Any]]:
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text())
    rows = post_json(payload)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(rows, separators=(",", ":")) + "\n")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(rows[0])
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def load_population(data_dir: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    quality = read_csv(data_dir / "quality" / "account_quality.csv")
    eligible = {row["wallet"].lower() for row in quality if not eligibility_reasons(row)}
    aliases = anonymized_aliases([row["wallet"].lower() for row in quality])
    episodes = [
        row for row in read_csv(data_dir / "processed" / "position_episodes.csv")
        if row["wallet"].lower() in eligible
        and row["closed"].lower() == "true"
        and row["left_censored"].lower() == "false"
    ]
    episodes.sort(key=lambda row: (aliases[row["wallet"].lower()], int(row["first_entry_time"]), row["coin"]))
    if len(eligible) != 10 or len(episodes) != 61:
        raise RuntimeError(f"unexpected population: wallets={len(eligible)}, episodes={len(episodes)}")
    return episodes, aliases


def build_rows(data_dir: Path, cache_dir: Path, refresh: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    episodes, aliases = load_population(data_dir)
    counters: dict[str, int] = defaultdict(int)
    by_coin: dict[str, list[dict[str, str]]] = defaultdict(list)
    for episode in episodes:
        by_coin[episode["coin"]].append(episode)

    source_rows = []
    market: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]], str]] = {}
    for coin, items in sorted(by_coin.items()):
        start = min(expected_entry_bars(int(row["first_entry_time"]))[0] for row in items)
        end = max(expected_post_bars(int(row["first_entry_time"]))[-1] + FIVE_MINUTES_MS - 1 for row in items)
        error = ""
        try:
            candles = load_or_fetch(
                cache_dir / f"candles_5m_{cache_name(coin)}.json",
                {"type": "candleSnapshot", "req": {"coin": coin, "interval": "5m", "startTime": start, "endTime": end}},
                refresh,
            )
            funding = load_or_fetch(
                cache_dir / f"funding_{cache_name(coin)}.json",
                {"type": "fundingHistory", "coin": coin, "startTime": start - 2 * ONE_HOUR_MS, "endTime": end},
                refresh,
            )
        except Exception as exc:
            candles, funding, error = [], [], f"api_error:{type(exc).__name__}"
        market[coin] = candles, funding, error
        source_rows.append({
            "coin": coin,
            "episode_count": len(items),
            "requested_start": iso(start),
            "requested_end": iso(end),
            "candle_rows": len(candles),
            "funding_rows": len(funding),
            "mark_source": "unavailable",
            "oi_source": "unavailable",
            "fetch_error": error,
        })

    rows = []
    for episode in episodes:
        wallet = episode["wallet"].lower()
        alias = aliases[wallet]
        counters[alias] += 1
        episode_id = f"{alias}-M{counters[alias]:03d}"
        entry = int(episode["first_entry_time"])
        exit_ms = int(episode["last_exit_time"])
        pre = expected_entry_bars(entry)
        post = expected_post_bars(entry)
        candles, funding_rows, fetch_error = market[episode["coin"]]
        pre_count, pre_ratio = bar_coverage(candles, pre)
        post_count, post_ratio = bar_coverage(candles, post)
        funding = past_funding(funding_rows, entry)
        funding_ratio = 1.0 if funding and entry - int(funding["time"]) <= 2 * ONE_HOUR_MS else 0.0
        missing = []
        reasons = []
        if pre_ratio < 1.0:
            missing.extend(["ohlcv", "volume"])
            reasons.append("candle_5000_limit_or_market_unavailable")
        if funding_ratio < 1.0:
            missing.append("funding")
            reasons.append("no_past_funding_within_2h")
        missing.extend(["mark", "oi"])
        reasons.extend(["historical_mark_series_unavailable", "historical_oi_series_unavailable"])
        if fetch_error:
            reasons.append(fetch_error)
        # Historical mark and OI are required for FEATURE_READY.  Complete OHLCV
        # remains useful but is explicitly PARTIAL until those series exist.
        status = "PARTIAL" if pre_ratio == 1.0 else "NOT_READY"
        rows.append({
            "episode_id": episode_id,
            "account_alias": alias,
            "coin": episode["coin"],
            "side": episode["direction"],
            "entry_time": iso(entry),
            "exit_time": iso(exit_ms),
            "required_start": iso(pre[0]),
            "required_end_exclusive": iso(floor_5m(entry)),
            "entry_bar_excluded": "True",
            "entry_pre_expected_bars": len(pre),
            "entry_pre_ohlcv_bars": pre_count,
            "ohlcv_coverage_ratio": f"{pre_ratio:.6f}",
            "volume_coverage_ratio": f"{pre_ratio:.6f}",
            "mark_coverage_ratio": "",
            "oi_coverage_ratio": "",
            "funding_coverage_ratio": f"{funding_ratio:.6f}",
            "funding_observation_time": iso(int(funding["time"])) if funding else "",
            "evaluation_post_expected_bars": len(post),
            "evaluation_post_ohlcv_bars": post_count,
            "evaluation_post_ohlcv_coverage_ratio": f"{post_ratio:.6f}",
            "missing_series": ",".join(dict.fromkeys(missing)),
            "missing_reason": ",".join(dict.fromkeys(reasons)),
            "availability_status": status,
            "allowed_past_only_features": "price_returns,volume" if status == "PARTIAL" else "",
        })
    return rows, source_rows


def summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "series": series,
            "complete_episodes": sum(float(row[field]) == 1.0 for row in rows if row[field] != ""),
            "unavailable_episodes": sum(row[field] == "" for row in rows),
            "incomplete_episodes": sum(row[field] != "" and float(row[field]) < 1.0 for row in rows),
        }
        for series, field in [
            ("ohlcv", "ohlcv_coverage_ratio"),
            ("volume", "volume_coverage_ratio"),
            ("mark", "mark_coverage_ratio"),
            ("oi", "oi_coverage_ratio"),
            ("funding", "funding_coverage_ratio"),
            ("evaluation_post_ohlcv", "evaluation_post_ohlcv_coverage_ratio"),
        ]
    ]


def write_report(path: Path, rows: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
    statuses = Counter(row["availability_status"] for row in rows)
    coins_complete = sum(int(row["candle_rows"]) > 0 for row in sources)
    lines = [
        "# Market coverage review — 2026-10-02",
        "",
        "## Result",
        "",
        f"All {len(rows)} eligible completed episodes have an explicit coverage state: FEATURE_READY {statuses['FEATURE_READY']}, PARTIAL {statuses['PARTIAL']}, NOT_READY {statuses['NOT_READY']}.",
        "",
        "This is a coverage audit, not a behavior classification. FOMO, Late, averaging down, Revenge, Trapped, Crowding, and liquidation labels were not computed.",
        "",
        "| state | episodes | interpretation |",
        "|---|---:|---|",
        f"| FEATURE_READY | {statuses['FEATURE_READY']} | Complete past-only OHLCV, volume, mark, OI, and Funding |",
        f"| PARTIAL | {statuses['PARTIAL']} | Complete past-only candles; only price-return/volume features are allowed |",
        f"| NOT_READY | {statuses['NOT_READY']} | Entry lookback candle window is incomplete; excluded from market-feature analysis |",
        "",
        "## Window contract",
        "",
        "- Entry features use exactly 12 completed 5-minute bars ending at the floor of entry time. The candle containing entry is excluded.",
        "- Entry-minus-5m, 15m, and 60m are nested inside that past-only window.",
        "- The 12 bars after the entry boundary are stored only under `evaluation_post_*`; they never affect entry availability.",
        "- Funding is available only when the latest observation at or before entry is no more than two hours old.",
        "- Missing values are empty/NULL, never numeric zero. In particular historical mark and OI remain unavailable.",
        "",
        "## Source limits",
        "",
        f"- Official candle/Funding requests returned at least one candle for {coins_complete}/{len(sources)} episode coins.",
        "- The Info API exposes current mark/OI through `metaAndAssetCtxs`, not a historical time-range endpoint.",
        "- The official archive can contain `asset_ctxs`, but it is uploaded approximately monthly, may be delayed, and may have missing data. No verified archive rows for this PoC interval were available in the project cache, so mark/OI were not inferred.",
        "- The candle endpoint exposes only the most recent 5,000 candles. Old episodes outside that range remain NOT_READY.",
        "",
        "Official references:",
        "- https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint",
        "- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals",
        "- https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data",
        "",
        "## Artifacts",
        "",
        "- `episode_market_coverage.csv`: all episode-level windows, ratios, NULLs, reasons, and states",
        "- `series_coverage_summary.csv`: complete/unavailable/incomplete counts by series",
        "- `coin_source_coverage.csv`: requested interval and returned row counts by coin",
        "",
        "## Gate decision",
        "",
        "The market-coverage inventory is complete, but the full market-feature gate is not. FEATURE_READY is zero while historical mark/OI are unavailable. PARTIAL episodes may be used only for explicitly named price-return and volume features; they must not silently enter OI/crowding/mark-dependent analyses.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit past-only market-series coverage for eligible youbun episodes.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    rows, sources = build_rows(args.data, args.cache, args.refresh)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "episode_market_coverage.csv", rows)
    write_csv(args.output / "series_coverage_summary.csv", summary_rows(rows))
    write_csv(args.output / "coin_source_coverage.csv", sources)
    write_report(args.output / "README.md", rows, sources)


if __name__ == "__main__":
    main()
