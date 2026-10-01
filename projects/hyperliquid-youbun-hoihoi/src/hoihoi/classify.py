from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone


MAJORS = {"BTC", "ETH"}


def f(value, default=0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def classify_wallet(wallet: str, fills: list[dict], perp_state: dict, spot_state: dict,
                    discovered_at: datetime, source: dict, config: dict,
                    small_alt_symbols: set[str] | None = None) -> dict:
    now_ms = int(discovered_at.timestamp() * 1000)
    cutoff = now_ms - int(config["activity"]["lookback_days"]) * 86_400_000
    recent = [x for x in fills if f(x.get("time")) >= cutoff]
    perp = [x for x in recent if not str(x.get("coin", "")).startswith("@")]
    spot = [x for x in recent if str(x.get("coin", "")).startswith("@")]
    times = sorted(int(f(x.get("time"))) for x in perp)
    active_dates = {datetime.fromtimestamp(t / 1000, timezone.utc).date() for t in times}
    intervals = [(b - a) / 1000 for a, b in zip(times, times[1:]) if b > a]
    notionals = [abs(f(x.get("px")) * f(x.get("sz"))) for x in perp]
    symbols = Counter(str(x.get("coin")) for x in perp)
    side_notional = defaultdict(float)
    maker = 0
    for x in perp:
        notional = abs(f(x.get("px")) * f(x.get("sz")))
        side_notional[str(x.get("side"))] += notional
        maker += not bool(x.get("crossed"))
    total_notional = sum(notionals)
    long_ratio = side_notional["B"] / total_notional if total_notional else None
    major_ratio = sum(n for s, n in ((str(x.get("coin")), abs(f(x.get("px"))*f(x.get("sz")))) for x in perp)
                      if s in MAJORS) / total_notional if total_notional else None
    small_alt_symbols = small_alt_symbols or set()
    small_alt_ratio = sum(n for s, n in ((str(x.get("coin")), abs(f(x.get("px"))*f(x.get("sz")))) for x in perp)
                          if s in small_alt_symbols) / total_notional if total_notional else None
    positions = [p.get("position", {}) for p in perp_state.get("assetPositions", [])]
    positions = [p for p in positions if abs(f(p.get("szi"))) > 1e-12]
    equity = f((perp_state.get("marginSummary") or {}).get("accountValue"), None)
    total_exposure = sum(abs(f(p.get("positionValue"))) for p in positions)
    leverages = [f((p.get("leverage") or {}).get("value")) for p in positions]
    effective_leverage = total_exposure / equity if equity and equity > 0 else None
    median_notional = statistics.median(notionals) if notionals else None
    median_interval = statistics.median(intervals) if intervals else None
    maker_ratio = maker / len(perp) if perp else None
    fills_per_day = len(perp) / max(len(active_dates), 1)
    c = config["classification"]
    bot = len(perp) >= c["high_frequency_fills_30d"] and (
        fills_per_day >= c["bot_fills_per_active_day"] or
        (median_interval is not None and median_interval <= c["bot_median_interval_seconds"])
    )
    both_sides = side_notional["B"] > 0 and side_notional["A"] > 0
    mm = bool(bot and both_sides and maker_ratio is not None and maker_ratio >= c["mm_maker_ratio"])
    farm = bool(len(perp) >= c["high_frequency_fills_30d"] and median_notional is not None
                and median_notional <= c["farm_max_median_notional"] and len(symbols) >= c["farm_min_symbols"])
    spot_balances = {str(b.get("coin")): f(b.get("total")) for b in spot_state.get("balances", []) if f(b.get("total")) > 0}
    funding_arb_reasons = []
    for p in positions:
        coin, size = str(p.get("coin")), f(p.get("szi"))
        if size < 0 and spot_balances.get(coin, 0) > 0:
            ratio = spot_balances[coin] / abs(size)
            if 0.7 <= ratio <= 1.3:
                funding_arb_reasons.append(f"{coin}: spot/perp hedge size ratio={ratio:.2f}")
    funding_arb = bool(funding_arb_reasons)
    arb = funding_arb
    exclusion_reasons = []
    for flag, label in ((bot, "BOT_SUSPECTED"), (mm, "MM_SUSPECTED"), (arb, "ARBITRAGE_SUSPECTED"),
                        (funding_arb, "FUNDING_ARBITRAGE_SUSPECTED"), (farm, "FARM_SUSPECTED")):
        if flag:
            exclusion_reasons.append(label)
    size_class = ("unknown" if median_notional is None else "small" if median_notional < c["small_median_notional"]
                  else "large" if median_notional >= c["large_median_notional"] else "medium")
    frequency_class = "low" if len(perp) < c["low_frequency_fills_30d"] else "high" if len(perp) >= c["high_frequency_fills_30d"] else "medium"
    leverage_class = "unknown" if effective_leverage is None else "high" if effective_leverage >= c["high_leverage"] else "low" if effective_leverage <= c["low_leverage"] else "medium"
    activity_ok = len(perp) >= config["activity"]["min_perp_fills"]
    status = "OBSERVING" if activity_ok else "INACTIVE"
    if major_ratio is None:
        symbol_profile = "unknown"
    elif major_ratio >= c["major_ratio"]:
        symbol_profile = "btc_eth_core"
    elif small_alt_ratio is not None and small_alt_ratio >= .50:
        symbol_profile = "small_alt_core"
    else:
        symbol_profile = "alt_core"
    hours = Counter(datetime.fromtimestamp(t / 1000, timezone.utc).hour for t in times)
    if hours:
        h_jst = (hours.most_common(1)[0][0] + 9) % 24
        activity_time_band = "jst_00_05" if h_jst < 6 else "jst_06_11" if h_jst < 12 else "jst_12_17" if h_jst < 18 else "jst_18_23"
    else:
        activity_time_band = "unknown"
    active_days_band = "none" if not active_dates else "1_3" if len(active_dates) <= 3 else "4_10" if len(active_dates) <= 10 else "11_plus"
    return {
        "wallet": wallet, "schema_version": config["schema_version"], "status": status,
        "first_seen": discovered_at.isoformat(), "last_seen": discovered_at.isoformat(),
        "discovery_source": source["source"], "discovery_detail": source["source_detail"],
        "leaderboard_rank": source.get("leaderboard_rank"),
        "leaderboard_rank_band": source.get("leaderboard_rank_band", "not_ranked"),
        "active_days_30d": len(active_dates), "trade_count_observed": len(fills),
        "trade_count_30d": len(recent), "perp_trade_count_30d": len(perp), "spot_trade_count_30d": len(spot),
        "estimated_volume_30d": total_notional, "median_trade_size": median_notional,
        "open_position_count": len(positions), "total_exposure": total_exposure,
        "equity": equity, "cash_balance": f((perp_state.get("marginSummary") or {}).get("totalRawUsd"), None),
        "unrealized_pnl": sum(f(p.get("unrealizedPnl")) for p in positions),
        "margin_usage": f((perp_state.get("marginSummary") or {}).get("totalMarginUsed"), None),
        "max_leverage": max(leverages) if leverages else None, "effective_leverage": effective_leverage,
        "long_trade_notional_ratio": long_ratio, "symbols_count": len(symbols),
        "main_symbols": ",".join(x[0] for x in symbols.most_common(5)),
        "btc_eth_ratio": major_ratio, "alt_ratio": None if major_ratio is None else 1 - major_ratio,
        "small_alt_ratio": small_alt_ratio, "symbol_profile": symbol_profile,
        "activity_time_band": activity_time_band, "active_days_band": active_days_band,
        "median_interval_seconds": median_interval, "fills_per_active_day": fills_per_day,
        "maker_ratio": maker_ratio, "perp_usage_ratio": len(perp) / len(recent) if recent else None,
        "spot_usage_ratio": len(spot) / len(recent) if recent else None,
        "size_class": size_class, "frequency_class": frequency_class, "leverage_class": leverage_class,
        "bot_suspected": bot, "mm_suspected": mm, "arbitrage_suspected": arb,
        "funding_arbitrage_suspected": funding_arb, "farm_suspected": farm,
        "suspicion_reason": "; ".join(exclusion_reasons + funding_arb_reasons),
        "eligible_after": None, "sample_version": None, "sample_created_at": None,
        "data_complete": len(fills) < 2000, "data_limit_note": "userFills capped at 2000" if len(fills) >= 2000 else "",
    }


def depletion_status(previous: dict | None, current: dict, ledger_updates: list[dict], config: dict) -> tuple[str, str]:
    if not previous:
        return "NONE", "no prior weekly snapshot"
    old, new = f(previous.get("equity"), None), f(current.get("equity"), None)
    if old is None or new is None or old <= 0:
        return "UNKNOWN", "missing comparable equity"
    drop = (old - new) / old
    withdrawals = 0.0
    for row in ledger_updates:
        delta = row.get("delta") or {}
        if "withdraw" in str(delta).lower():
            withdrawals += abs(f(delta.get("usd") or delta.get("amount") or 0))
    if withdrawals and abs((old - new) - withdrawals) <= max(withdrawals, 1) * config["depletion"]["withdrawal_match_tolerance"]:
        return "WITHDRAWAL_SUSPECTED", f"equity drop {drop:.1%}; withdrawal-like ledger {withdrawals:.2f}"
    if drop >= config["depletion"]["rapid_fraction"]:
        return "RAPID_DEPLETION", f"equity drop {drop:.1%}"
    if drop >= config["depletion"]["near_fraction"]:
        return "NEAR_DEPLETION", f"equity drop {drop:.1%}"
    return "NONE", f"equity drop {drop:.1%}"
