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
    spot_pairs: dict[str, str],
    settings: Settings,
    logger: Any,
) -> dict[str, Any]:
    orders: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    wallet_by_address = {wallet["address"].lower(): wallet for wallet in wallets}
    total = len(wallets)

    for index, wallet in enumerate(wallets, start=1):
        address = wallet["address"]
        logger.info(f"未約定注文取得 {index}/{total}: {wallet['cohort_label']} #{wallet['rank']} {short_addr(address)}")
        try:
            raw_orders = client.frontend_open_orders(address)
            for raw_order in raw_orders:
                normalized = normalize_order(
                    raw_order=raw_order,
                    wallet=wallet,
                    mids=mids,
                    spot_pairs=spot_pairs,
                    target_symbols=settings.target_symbols,
                )
                if normalized is not None:
                    orders.append(normalized)
        except Exception as exc:
            logger.warning(f"未約定注文取得エラー: {short_addr(address)} error={exc}")
            errors.append({"address": address, "cohort": wallet["cohort"], "rank": wallet["rank"], "error": str(exc)})
        time.sleep(settings.request_sleep_seconds)

    return {
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "target_symbols": list(settings.target_symbols),
        "leaderboard_limit": settings.leaderboard_limit,
        "mids": {symbol: mids.get(symbol) for symbol in settings.target_symbols},
        "wallets": list(wallet_by_address.values()),
        "orders": orders,
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


def build_report(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    current_orders = current.get("orders", [])
    previous_orders = previous.get("orders", []) if previous else []

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

    return {
        "as_of_utc": current.get("as_of_utc"),
        "previous_as_of_utc": previous.get("as_of_utc") if previous else None,
        "has_previous_snapshot": previous is not None,
        "mids": current.get("mids", {}),
        "stats": {
            "current_orders": len(current_orders),
            "previous_orders": len(previous_orders),
            "new_orders": len(new_orders),
            "cancelled_orders": len(cancelled_orders),
            "persisted_orders": len(persisted_orders),
            "entered_watch_orders": len(entered_watch_orders),
            "left_watch_orders": len(left_watch_orders),
            "errors": len(current.get("errors", [])),
        },
        "changes": changes,
        "active": active,
        "errors": current.get("errors", []),
    }


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
