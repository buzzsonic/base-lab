from __future__ import annotations

import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .config import Settings


def build_snapshot(
    client: Any,
    wallets: list[dict[str, Any]],
    mids: dict[str, float],
    market_contexts: dict[str, dict[str, Any]],
    settings: Settings,
    logger: Any,
) -> dict[str, Any]:
    orders: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    wallet_by_address = {wallet["address"].lower(): wallet for wallet in wallets}
    total = len(wallets)

    for index, wallet in enumerate(wallets, start=1):
        address = wallet["address"]
        logger.info(f"ウォレット情報取得 {index}/{total}: {wallet['cohort_label']} #{wallet['rank']} {short_addr(address)}")
        try:
            state = client.clearinghouse_state(address)
            for raw_position in state.get("assetPositions", []):
                normalized_position = normalize_position(
                    raw_position=raw_position,
                    wallet=wallet,
                    mids=mids,
                    target_symbols=settings.target_symbols,
                )
                if normalized_position is not None:
                    positions.append(normalized_position)
        except Exception as exc:
            logger.warning(f"ポジション取得エラー: {short_addr(address)} error={exc}")
            errors.append(
                {
                    "address": address,
                    "cohort": wallet["cohort"],
                    "rank": wallet["rank"],
                    "kind": "positions",
                    "error": str(exc),
                }
            )
        time.sleep(settings.request_sleep_seconds)

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "target_symbols": list(settings.target_symbols),
        "leaderboard_limit": settings.leaderboard_limit,
        "mids": {symbol: mids.get(symbol) for symbol in settings.target_symbols},
        "market_contexts": {symbol: market_contexts.get(symbol, {}) for symbol in settings.target_symbols},
        "wallets": list(wallet_by_address.values()),
        "orders": orders,
        "positions": positions,
        "errors": errors,
    }


def normalize_order(
    raw_order: dict[str, Any],
    wallet: dict[str, Any],
    mids: dict[str, float],
    spot_pairs: dict[str, str],
    target_symbols: tuple[str, ...],
) -> dict[str, Any] | None:
    coin = str(raw_order.get("coin") or "")
    coin_display = coin_display_name(coin, spot_pairs)
    market = target_market(coin=coin, coin_display=coin_display, target_symbols=target_symbols)
    if market is None:
        return None

    limit_px = to_float(raw_order.get("limitPx"))
    size = to_float(raw_order.get("sz"))
    if limit_px is None or size is None or limit_px <= 0 or size <= 0:
        return None

    mid_px = mids.get(coin)
    distance_pct = ((limit_px - mid_px) / mid_px) if mid_px else None
    side = side_label(raw_order.get("side"))
    oid = raw_order.get("oid")
    address = wallet["address"].lower()

    return {
        "key": f"{address}:{oid}",
        "address": address,
        "wallet": short_addr(address),
        "rank": wallet.get("rank"),
        "cohort": wallet.get("cohort"),
        "cohort_label": wallet.get("cohort_label"),
        "display_name": wallet.get("display_name"),
        "pnl_30d": wallet.get("pnl_30d"),
        "roi_30d": wallet.get("roi_30d"),
        "coin": coin,
        "coin_display": coin_display,
        "market": market,
        "side": side,
        "limit_px": limit_px,
        "mid_px": mid_px,
        "distance_pct": distance_pct,
        "abs_distance_pct": abs(distance_pct) if distance_pct is not None else None,
        "size": size,
        "notional_usd": abs(limit_px * size),
        "order_type": raw_order.get("orderType"),
        "reduce_only": bool(raw_order.get("reduceOnly")),
        "is_trigger": bool(raw_order.get("isTrigger")),
        "trigger_px": to_float(raw_order.get("triggerPx")),
        "trigger_condition": raw_order.get("triggerCondition"),
        "oid": oid,
        "timestamp_ms": raw_order.get("timestamp"),
    }


def normalize_position(
    raw_position: dict[str, Any],
    wallet: dict[str, Any],
    mids: dict[str, float],
    target_symbols: tuple[str, ...],
) -> dict[str, Any] | None:
    position = raw_position.get("position") if isinstance(raw_position, dict) else None
    if not isinstance(position, dict):
        return None

    coin = str(position.get("coin") or "")
    market = target_market(coin=coin, coin_display=coin, target_symbols=target_symbols)
    if market is None:
        return None

    size = to_float(position.get("szi"))
    if size is None or abs(size) <= 0:
        return None

    entry_px = to_float(position.get("entryPx"))
    position_value = to_float(position.get("positionValue"))
    if position_value is None:
        mark = mids.get(coin) or entry_px
        position_value = abs(size * mark) if mark is not None else 0.0
    position_value = abs(position_value)

    side = "LONG" if size > 0 else "SHORT"
    address = wallet["address"].lower()

    return {
        "key": f"{address}:{market}:{side}",
        "address": address,
        "wallet": short_addr(address),
        "rank": wallet.get("rank"),
        "cohort": wallet.get("cohort"),
        "cohort_label": wallet.get("cohort_label"),
        "display_name": wallet.get("display_name"),
        "market": market,
        "coin": coin,
        "side": side,
        "size": size,
        "abs_size": abs(size),
        "notional_usd": position_value,
        "entry_px": entry_px,
        "unrealized_pnl": to_float(position.get("unrealizedPnl")),
        "liquidation_px": to_float(position.get("liquidationPx")),
    }


def build_report(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    current_orders = current.get("orders", [])
    previous_orders = previous.get("orders", []) if previous else []
    current_positions = current.get("positions", [])
    has_previous_positions = previous is not None and isinstance(previous.get("positions"), list)
    previous_positions = previous.get("positions", []) if has_previous_positions else []
    current_market_contexts = current.get("market_contexts", {})
    previous_market_contexts = previous.get("market_contexts", {}) if previous else {}
    has_previous_market_contexts = previous is not None and isinstance(previous.get("market_contexts"), dict)

    current_by_key = {row["key"]: row for row in current_orders if row.get("key")}
    previous_by_key = {row["key"]: row for row in previous_orders if row.get("key")}

    new_orders = [current_by_key[key] for key in current_by_key.keys() - previous_by_key.keys()]
    cancelled_orders = [previous_by_key[key] for key in previous_by_key.keys() - current_by_key.keys()]
    persisted_orders = [current_by_key[key] for key in current_by_key.keys() & previous_by_key.keys()]
    entered_watch_orders = [
        current_by_key[key]
        for key in current_by_key.keys() & previous_by_key.keys()
        if not in_band(previous_by_key[key], settings.watch_band_pct) and in_band(current_by_key[key], settings.watch_band_pct)
    ]
    left_watch_orders = [
        current_by_key[key]
        for key in current_by_key.keys() & previous_by_key.keys()
        if in_band(previous_by_key[key], settings.watch_band_pct) and not in_band(current_by_key[key], settings.watch_band_pct)
    ]

    changes = build_change_rows(
        new_orders=new_orders,
        cancelled_orders=cancelled_orders,
        entered_watch_orders=entered_watch_orders,
        left_watch_orders=left_watch_orders,
        settings=settings,
    )
    active = build_active_rows(current_orders=current_orders, settings=settings)
    position_rows = build_position_rows(current_positions=current_positions)
    position_change_rows = (
        build_position_change_rows(
            current_positions=current_positions,
            previous_positions=previous_positions,
            settings=settings,
        )
        if has_previous_positions
        else []
    )
    market_rows = build_market_rows(
        current_market_contexts=current_market_contexts,
        previous_market_contexts=previous_market_contexts,
        settings=settings,
    )
    liquidation_levels = build_liquidation_levels(
        current_positions=current_positions,
        market_contexts=current_market_contexts,
        settings=settings,
    )

    return {
        "as_of_utc": current.get("as_of_utc"),
        "previous_as_of_utc": previous.get("as_of_utc") if previous else None,
        "has_previous_snapshot": previous is not None,
        "has_previous_position_snapshot": has_previous_positions,
        "has_previous_market_contexts": has_previous_market_contexts,
        "mids": current.get("mids", {}),
        "stats": {
            "current_orders": len(current_orders),
            "previous_orders": len(previous_orders),
            "new_orders": len(new_orders),
            "cancelled_orders": len(cancelled_orders),
            "persisted_orders": len(persisted_orders),
            "entered_watch_orders": len(entered_watch_orders),
            "left_watch_orders": len(left_watch_orders),
            "current_positions": len(current_positions),
            "previous_positions": len(previous_positions),
            "markets": len(market_rows),
            "liquidation_levels": sum(len(rows) for sides in liquidation_levels.values() for rows in sides.values()),
            "errors": len(current.get("errors", [])),
        },
        "changes": changes,
        "active": active,
        "positions": position_rows,
        "position_changes": position_change_rows,
        "markets": market_rows,
        "liquidation_levels": liquidation_levels,
        "errors": current.get("errors", []),
    }


def build_market_rows(
    current_market_contexts: dict[str, Any],
    previous_market_contexts: dict[str, Any],
    settings: Settings,
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for market in settings.target_symbols:
        current = current_market_contexts.get(market, {}) if isinstance(current_market_contexts, dict) else {}
        previous = previous_market_contexts.get(market, {}) if isinstance(previous_market_contexts, dict) else {}
        if not isinstance(current, dict):
            current = {}
        if not isinstance(previous, dict):
            previous = {}

        oi_usd = to_float(current.get("open_interest_usd"))
        previous_oi_usd = to_float(previous.get("open_interest_usd"))
        oi_delta_usd = None
        oi_delta_pct = None
        if oi_usd is not None and previous_oi_usd is not None:
            oi_delta_usd = oi_usd - previous_oi_usd
            oi_delta_pct = oi_delta_usd / previous_oi_usd if previous_oi_usd else None

        rows[market] = {
            "market": market,
            "mark_px": to_float(current.get("mark_px")),
            "mid_px": to_float(current.get("mid_px")),
            "oracle_px": to_float(current.get("oracle_px")),
            "funding": to_float(current.get("funding")),
            "open_interest_coin": to_float(current.get("open_interest_coin")),
            "open_interest_usd": oi_usd,
            "previous_open_interest_usd": previous_oi_usd,
            "oi_delta_usd": oi_delta_usd,
            "oi_delta_pct": oi_delta_pct,
            "oi_alert": oi_delta_usd is not None and abs(oi_delta_usd) >= settings.min_oi_delta_usd,
        }
    return rows


def build_liquidation_levels(
    current_positions: list[dict[str, Any]],
    market_contexts: dict[str, Any],
    settings: Settings,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, float], dict[str, Any]] = defaultdict(_empty_liquidation_row)

    for position in current_positions:
        market = position.get("market")
        if not market:
            continue
        context = market_contexts.get(market, {}) if isinstance(market_contexts, dict) else {}
        mark_px = to_float(context.get("mark_px")) if isinstance(context, dict) else None
        if mark_px is None:
            mark_px = to_float(position.get("mid_px"))
        liquidation_px = to_float(position.get("liquidation_px"))
        if mark_px is None or mark_px <= 0 or liquidation_px is None or liquidation_px <= 0:
            continue

        distance_pct = liquidation_px / mark_px - 1
        if abs(distance_pct) > settings.liquidation_band_pct / 100:
            continue

        side = str(position.get("side") or "").upper()
        if side == "SHORT":
            direction = "above"
        elif side == "LONG":
            direction = "below"
        else:
            direction = "above" if distance_pct > 0 else "below"

        bucket_px = liquidation_bucket_price(
            price=liquidation_px,
            mark_px=mark_px,
            bucket_pct=settings.liquidation_bucket_pct,
        )
        key = (market, direction, bucket_px)
        row = grouped[key]
        row["market"], row["direction"], row["bucket_px"] = key
        notional = float(position.get("notional_usd") or 0)
        row["notional_usd"] += notional
        row["wallets"].add(position.get("address"))
        row["liquidation_prices"].append(liquidation_px)
        row["distances"].append(distance_pct)
        row["weighted_distance"] += distance_pct * notional
        row["distance_weight"] += notional
        cohort = position.get("cohort")
        if cohort == "winner":
            row["winner_usd"] += notional
        elif cohort == "loser":
            row["loser_usd"] += notional

    levels: dict[str, dict[str, list[dict[str, Any]]]] = {
        market: {"above": [], "below": []} for market in settings.target_symbols
    }
    for row in grouped.values():
        prices = row.pop("liquidation_prices")
        distances = row.pop("distances")
        wallets = {wallet for wallet in row.pop("wallets") if wallet}
        row["wallet_count"] = len(wallets)
        row["min_px"] = min(prices) if prices else None
        row["max_px"] = max(prices) if prices else None
        row["avg_distance_pct"] = weighted_average(row.pop("weighted_distance"), row.pop("distance_weight"))
        if row["avg_distance_pct"] is None and distances:
            row["avg_distance_pct"] = statistics.mean(distances)
        row["alert"] = row["notional_usd"] >= settings.min_liquidation_usd
        levels.setdefault(row["market"], {"above": [], "below": []})
        levels[row["market"]][row["direction"]].append(row)

    for market_levels in levels.values():
        for direction in ("above", "below"):
            market_levels[direction].sort(
                key=lambda row: (
                    not row["alert"],
                    -row["notional_usd"],
                    abs(row.get("avg_distance_pct") or 0),
                )
            )
    return levels


def liquidation_bucket_price(price: float, mark_px: float, bucket_pct: float) -> float:
    bucket_size = mark_px * bucket_pct / 100
    if bucket_size <= 0:
        return price
    return round(price / bucket_size) * bucket_size


def build_position_rows(current_positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(_empty_position_row)
    for position in current_positions:
        key = (position["market"], position["cohort"])
        row = grouped[key]
        row["market"], row["cohort"] = key
        side = position["side"].lower()
        notional = float(position.get("notional_usd") or 0)
        row[f"{side}_usd"] += notional
        row[f"{side}_wallets"].add(position["address"])
        entry_px = position.get("entry_px")
        if entry_px is not None:
            row[f"{side}_entry_weighted"] += float(entry_px) * notional
            row[f"{side}_entry_weight"] += notional

    rows = []
    for row in grouped.values():
        row["long_wallet_count"] = len(row.pop("long_wallets"))
        row["short_wallet_count"] = len(row.pop("short_wallets"))
        row["net_usd"] = row["long_usd"] - row["short_usd"]
        row["long_avg_entry"] = weighted_average(row.pop("long_entry_weighted"), row.pop("long_entry_weight"))
        row["short_avg_entry"] = weighted_average(row.pop("short_entry_weighted"), row.pop("short_entry_weight"))
        rows.append(row)
    rows.sort(key=lambda row: (row["market"], row["cohort"]))
    return rows


def build_position_change_rows(
    current_positions: list[dict[str, Any]],
    previous_positions: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    current_by_wallet = position_wallet_map(current_positions)
    previous_by_wallet = position_wallet_map(previous_positions)
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(_empty_position_change_row)

    for key in current_by_wallet.keys() | previous_by_wallet.keys():
        market, cohort, address = key
        current = current_by_wallet.get(key, {"long_usd": 0.0, "short_usd": 0.0})
        previous = previous_by_wallet.get(key, {"long_usd": 0.0, "short_usd": 0.0})
        long_delta = current["long_usd"] - previous["long_usd"]
        short_delta = current["short_usd"] - previous["short_usd"]
        if abs(long_delta) < 1e-6 and abs(short_delta) < 1e-6:
            continue

        row = grouped[(market, cohort)]
        row["market"], row["cohort"] = market, cohort
        row["long_delta_usd"] += long_delta
        row["short_delta_usd"] += short_delta
        row["wallets"].add(address)

    rows = []
    for row in grouped.values():
        row["wallet_count"] = len(row.pop("wallets"))
        row["net_delta_usd"] = row["long_delta_usd"] - row["short_delta_usd"]
        row["alert"] = (
            abs(row["net_delta_usd"]) >= settings.min_active_usd
            or abs(row["long_delta_usd"]) >= settings.min_active_usd
            or abs(row["short_delta_usd"]) >= settings.min_active_usd
        )
        rows.append(row)
    rows.sort(key=lambda row: (-abs(row["net_delta_usd"]), row["market"], row["cohort"]))
    return rows


def position_wallet_map(positions: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, float]]:
    mapped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {"long_usd": 0.0, "short_usd": 0.0})
    for position in positions:
        key = (position["market"], position["cohort"], position["address"])
        side = position["side"].lower()
        mapped[key][f"{side}_usd"] += float(position.get("notional_usd") or 0)
    return dict(mapped)


def weighted_average(total: float, weight: float) -> float | None:
    if weight <= 0:
        return None
    return total / weight


def build_change_rows(
    new_orders: list[dict[str, Any]],
    cancelled_orders: list[dict[str, Any]],
    entered_watch_orders: list[dict[str, Any]],
    left_watch_orders: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(_empty_change_row)

    for event, orders in [
        ("new", new_orders),
        ("cancelled", cancelled_orders),
        ("entered_watch", entered_watch_orders),
        ("left_watch", left_watch_orders),
    ]:
        for order in orders:
            key = (order["market"], order["cohort"], order["side"])
            row = grouped[key]
            row["market"], row["cohort"], row["side"] = key
            row[f"{event}_count"] += 1
            row[f"{event}_usd"] += float(order.get("notional_usd") or 0)
            row["wallets"].add(order["address"])
            row["prices"].append(float(order["limit_px"]))
            distance = order.get("distance_pct")
            if distance is not None:
                row["distances"].append(float(distance))
            if in_band(order, settings.near_band_pct):
                row[f"{event}_near_usd"] += float(order.get("notional_usd") or 0)
                row["near_prices"].append(float(order["limit_px"]))
            if in_band(order, settings.watch_band_pct):
                row[f"{event}_watch_usd"] += float(order.get("notional_usd") or 0)
                row["watch_prices"].append(float(order["limit_px"]))

    rows = []
    for row in grouped.values():
        row["wallet_count"] = len(row.pop("wallets"))
        prices = row.pop("prices")
        near_prices = row.pop("near_prices")
        watch_prices = row.pop("watch_prices")
        distances = row.pop("distances")
        row["min_px"] = min(prices) if prices else None
        row["max_px"] = max(prices) if prices else None
        row["near_min_px"] = min(near_prices) if near_prices else None
        row["near_max_px"] = max(near_prices) if near_prices else None
        row["watch_min_px"] = min(watch_prices) if watch_prices else None
        row["watch_max_px"] = max(watch_prices) if watch_prices else None
        row["avg_distance_pct"] = statistics.mean(distances) if distances else None
        row["net_near_usd"] = row["new_near_usd"] - row["cancelled_near_usd"]
        row["net_watch_usd"] = row["new_watch_usd"] - row["cancelled_watch_usd"]
        row["alert"] = should_alert_change(row, settings)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            not row["alert"],
            -max(abs(row["net_near_usd"]), abs(row["net_watch_usd"]), row["new_watch_usd"], row["cancelled_watch_usd"]),
        )
    )
    return rows


def build_active_rows(current_orders: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(_empty_active_row)
    for order in current_orders:
        key = (order["market"], order["cohort"], order["side"])
        row = grouped[key]
        row["market"], row["cohort"], row["side"] = key
        notional = float(order.get("notional_usd") or 0)
        row["total_usd"] += notional
        row["count"] += 1
        row["wallets"].add(order["address"])
        row["prices"].append(float(order["limit_px"]))
        if in_band(order, settings.near_band_pct):
            row["near_usd"] += notional
            row["near_count"] += 1
            row["near_wallets"].add(order["address"])
            row["near_prices"].append(float(order["limit_px"]))
        if in_band(order, settings.watch_band_pct):
            row["watch_usd"] += notional
            row["watch_count"] += 1
            row["watch_wallets"].add(order["address"])
            row["watch_prices"].append(float(order["limit_px"]))

    rows = []
    for row in grouped.values():
        row["wallet_count"] = len(row.pop("wallets"))
        prices = row.pop("prices")
        near_prices = row.pop("near_prices")
        watch_prices = row.pop("watch_prices")
        near_wallets = row.pop("near_wallets")
        watch_wallets = row.pop("watch_wallets")
        row["min_px"] = min(prices) if prices else None
        row["max_px"] = max(prices) if prices else None
        row["near_min_px"] = min(near_prices) if near_prices else None
        row["near_max_px"] = max(near_prices) if near_prices else None
        row["watch_min_px"] = min(watch_prices) if watch_prices else None
        row["watch_max_px"] = max(watch_prices) if watch_prices else None
        row["near_wallet_count"] = len(near_wallets)
        row["watch_wallet_count"] = len(watch_wallets)
        row["alert"] = row["watch_usd"] >= settings.min_active_usd
        rows.append(row)
    rows.sort(key=lambda row: (-row["watch_usd"], -row["near_usd"], row["market"], row["cohort"], row["side"]))
    return rows


def should_alert_change(row: dict[str, Any], settings: Settings) -> bool:
    return (
        abs(row["net_near_usd"]) >= settings.min_near_change_usd
        or row["new_near_usd"] >= settings.min_near_change_usd
        or row["cancelled_near_usd"] >= settings.min_near_change_usd
        or abs(row["net_watch_usd"]) >= settings.min_watch_change_usd
        or row["new_watch_usd"] >= settings.min_watch_change_usd
        or row["cancelled_watch_usd"] >= settings.min_watch_change_usd
        or row["entered_watch_usd"] >= settings.min_near_change_usd
        or row["left_watch_usd"] >= settings.min_near_change_usd
    )


def _empty_change_row() -> dict[str, Any]:
    row: dict[str, Any] = {
        "market": "",
        "cohort": "",
        "side": "",
        "wallets": set(),
        "prices": [],
        "near_prices": [],
        "watch_prices": [],
        "distances": [],
    }
    for event in ["new", "cancelled", "entered_watch", "left_watch"]:
        row[f"{event}_count"] = 0
        row[f"{event}_usd"] = 0.0
        row[f"{event}_near_usd"] = 0.0
        row[f"{event}_watch_usd"] = 0.0
    return row


def _empty_active_row() -> dict[str, Any]:
    return {
        "market": "",
        "cohort": "",
        "side": "",
        "count": 0,
        "near_count": 0,
        "watch_count": 0,
        "total_usd": 0.0,
        "near_usd": 0.0,
        "watch_usd": 0.0,
        "wallets": set(),
        "near_wallets": set(),
        "watch_wallets": set(),
        "prices": [],
        "near_prices": [],
        "watch_prices": [],
    }


def _empty_position_row() -> dict[str, Any]:
    return {
        "market": "",
        "cohort": "",
        "long_usd": 0.0,
        "short_usd": 0.0,
        "long_wallets": set(),
        "short_wallets": set(),
        "long_entry_weighted": 0.0,
        "long_entry_weight": 0.0,
        "short_entry_weighted": 0.0,
        "short_entry_weight": 0.0,
    }


def _empty_position_change_row() -> dict[str, Any]:
    return {
        "market": "",
        "cohort": "",
        "long_delta_usd": 0.0,
        "short_delta_usd": 0.0,
        "net_delta_usd": 0.0,
        "wallets": set(),
        "wallet_count": 0,
        "alert": False,
    }


def _empty_liquidation_row() -> dict[str, Any]:
    return {
        "market": "",
        "direction": "",
        "bucket_px": 0.0,
        "notional_usd": 0.0,
        "winner_usd": 0.0,
        "loser_usd": 0.0,
        "wallets": set(),
        "liquidation_prices": [],
        "distances": [],
        "weighted_distance": 0.0,
        "distance_weight": 0.0,
        "wallet_count": 0,
        "alert": False,
    }


def in_band(order: dict[str, Any], band_pct: float) -> bool:
    distance = order.get("abs_distance_pct")
    return distance is not None and float(distance) <= band_pct / 100


def target_market(coin: str, coin_display: str, target_symbols: tuple[str, ...]) -> str | None:
    coin_upper = coin.upper()
    display_upper = coin_display.upper()
    base = display_upper.split("/", 1)[0]
    for target in target_symbols:
        if coin_upper == target:
            return target
        if base == target or base == f"U{target}":
            return target
    return None


def coin_display_name(coin: str, spot_pairs: dict[str, str]) -> str:
    if coin in spot_pairs:
        return f"{spot_pairs[coin]} ({coin})"
    return coin


def side_label(side: Any) -> str:
    if side == "B":
        return "BUY"
    if side == "A":
        return "SELL"
    return str(side or "").upper()


def to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def short_addr(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}" if address else ""
