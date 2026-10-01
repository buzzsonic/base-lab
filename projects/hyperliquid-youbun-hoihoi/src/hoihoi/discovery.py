from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_wallet(value: object) -> str | None:
    wallet = str(value or "").lower()
    return wallet if ADDRESS.fullmatch(wallet) else None


def _stable_order(wallet: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{wallet}".encode()).hexdigest()


def leaderboard_candidates(payload: dict, limit: int) -> list[dict]:
    """Take deterministic coverage across volume/equity strata, not PnL rank."""
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    all_rows = payload.get("leaderboardRows", [])
    total_rows = max(len(all_rows), 1)
    for rank, row in enumerate(all_rows, 1):
        wallet = normalize_wallet(row.get("ethAddress"))
        if not wallet:
            continue
        perfs = {x[0]: x[1] for x in row.get("windowPerformances", []) if isinstance(x, list) and len(x) == 2}
        month = perfs.get("month") or {}
        try:
            volume = float(month.get("vlm") or 0)
            equity = float(row.get("accountValue") or 0)
        except (TypeError, ValueError):
            continue
        volume_band = "v0" if volume < 1e5 else "v1" if volume < 1e6 else "v2" if volume < 1e7 else "v3"
        equity_band = "e0" if equity < 1e3 else "e1" if equity < 1e4 else "e2" if equity < 1e5 else "e3"
        rank_pct = rank / total_rows
        rank_band = "top_1pct" if rank_pct <= .01 else "top_10pct" if rank_pct <= .10 else "mid_40pct" if rank_pct <= .50 else "bottom_50pct"
        buckets[(volume_band, equity_band, rank_band)].append({
            "wallet": wallet, "source": "official_leaderboard",
            "source_detail": f"{volume_band}:{equity_band}:{rank_band}:rank={rank}",
            "source_volume_30d": volume, "source_equity": equity,
            "leaderboard_rank": rank, "leaderboard_rank_band": rank_band,
        })
    ordered_buckets = sorted(buckets)
    for key in ordered_buckets:
        buckets[key].sort(key=lambda x: _stable_order(x["wallet"], key[0] + key[1]))
    output, index = [], 0
    while len(output) < limit and ordered_buckets:
        key = ordered_buckets[index % len(ordered_buckets)]
        if buckets[key]:
            output.append(buckets[key].pop(0))
        else:
            ordered_buckets.remove(key)
            if not ordered_buckets:
                break
            index -= 1
        index += 1
    return output


def _time_band(hour_utc: int) -> str:
    hour_jst = (hour_utc + 9) % 24
    return "jst_00_05" if hour_jst < 6 else "jst_06_11" if hour_jst < 12 else "jst_12_17" if hour_jst < 18 else "jst_18_23"


def trade_stream_candidates(paths: list[Path], limit: int) -> list[dict]:
    """Stratify frozen public trades by time, symbol group and appearance frequency."""
    observations: dict[str, dict] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(errors="replace") as handle:
            for line in handle:
                try:
                    envelope = json.loads(line)
                    if envelope.get("channel") != "trades":
                        continue
                    wire = json.loads(envelope.get("wire") or "{}")
                    trades = wire.get("data") or []
                except (json.JSONDecodeError, TypeError):
                    continue
                for trade in trades:
                    coin = str(trade.get("coin") or "")
                    time_ms = int(trade.get("time") or envelope.get("source_time") or 0)
                    hour = (time_ms // 3_600_000) % 24 if time_ms else 0
                    symbol_group = "btc_eth" if coin in {"BTC", "ETH"} else "alt"
                    for role, raw in zip(("taker_or_buyer", "maker_or_seller"), trade.get("users") or []):
                        wallet = normalize_wallet(raw)
                        if wallet:
                            item = observations.setdefault(wallet, {"wallet": wallet, "count": 0, "time_bands": Counter(),
                                                                    "symbol_groups": Counter(), "roles": Counter()})
                            item["count"] += 1
                            item["time_bands"][_time_band(hour)] += 1
                            item["symbol_groups"][symbol_group] += 1
                            item["roles"][role] += 1
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for wallet, item in observations.items():
        count = item["count"]
        freq = "low" if count <= 2 else "medium" if count <= 10 else "high"
        time_band = item["time_bands"].most_common(1)[0][0]
        symbol_group = item["symbol_groups"].most_common(1)[0][0]
        row = {"wallet": wallet, "source": "public_trade_stream",
               "source_detail": f"time={time_band}:symbol={symbol_group}:event_freq={freq}:n={count}",
               "source_volume_30d": None, "source_equity": None, "leaderboard_rank": None,
               "leaderboard_rank_band": "not_ranked", "event_frequency_proxy": freq,
               "event_time_band": time_band, "event_symbol_group": symbol_group}
        buckets[(time_band, symbol_group, freq)].append(row)
    keys = sorted(buckets)
    for key in keys:
        buckets[key].sort(key=lambda x: _stable_order(x["wallet"], ":".join(key)))
    output, index = [], 0
    while keys and len(output) < limit:
        key = keys[index % len(keys)]
        if buckets[key]:
            output.append(buckets[key].pop(0))
        else:
            keys.remove(key)
            if not keys:
                break
            index -= 1
        index += 1
    return output


def merge_sources(sources: list[list[dict]], limit: int) -> list[dict]:
    """Round-robin sources and retain all discovery provenance on duplicates."""
    by_wallet: dict[str, dict] = {}
    active = [list(items) for items in sources]
    index = 0
    while active and len(by_wallet) < limit:
        bucket = active[index % len(active)]
        if not bucket:
            active.remove(bucket)
            if not active:
                break
            index -= 1
        else:
            row = bucket.pop(0)
            wallet = row["wallet"]
            if wallet in by_wallet:
                prior = by_wallet[wallet]
                prior["source"] += "+" + row["source"]
                prior["source_detail"] += ";" + row["source_detail"]
            else:
                by_wallet[wallet] = row
        index += 1
    return list(by_wallet.values())[:limit]
