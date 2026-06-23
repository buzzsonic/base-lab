from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from .config import Settings
from .logger import JST, UTC
from .models import AccountSnapshot, ClosedTrade, Fill, Position


@dataclass(frozen=True)
class PeriodWindow:
    label: str
    start_ms: int
    end_ms: int
    start_jst: datetime
    end_jst: datetime


def daily_window(now_jst: datetime, cutoff_hour: int, date_text: str | None = None) -> PeriodWindow:
    if date_text:
        day = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=JST)
    else:
        day = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = day.replace(hour=cutoff_hour, minute=0, second=0, microsecond=0)
    if not date_text and now_jst < end:
        end = now_jst
    return PeriodWindow(
        label=start.strftime("%Y-%m-%d"),
        start_ms=to_ms(start),
        end_ms=to_ms(end),
        start_jst=start,
        end_jst=end,
    )


def weekly_window(now_jst: datetime, report_weekday: int, notify_hour: int, date_text: str | None = None) -> PeriodWindow:
    anchor = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=JST) if date_text else now_jst
    week_start = (anchor - timedelta(days=anchor.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=report_weekday, hours=notify_hour)
    if not date_text and now_jst < week_end:
        week_end = now_jst
    return PeriodWindow(
        label=f"{week_start.strftime('%Y-%m-%d')}..{week_end.strftime('%Y-%m-%d')}",
        start_ms=to_ms(week_start),
        end_ms=to_ms(week_end),
        start_jst=week_start,
        end_jst=week_end,
    )


def to_ms(dt: datetime) -> int:
    return int(dt.astimezone(UTC).timestamp() * 1000)


def from_ms_jst(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, UTC).astimezone(JST)


def build_closed_trades(fills: list[Fill]) -> list[ClosedTrade]:
    lots: dict[tuple[str, str], deque[tuple[float, int, float]]] = defaultdict(deque)
    closed: list[ClosedTrade] = []

    for fill in sorted(fills, key=lambda row: row.time_ms):
        close_side = closed_side_from_direction(fill.direction)
        if close_side:
            hold_minutes = consume_open_lots(
                lots=lots[(fill.coin, close_side)],
                close_sz=fill.sz,
                close_time_ms=fill.time_ms,
            )
            closed.append(
                ClosedTrade(
                    coin=fill.coin,
                    side=close_side,
                    close_time_ms=fill.time_ms,
                    hold_minutes=hold_minutes,
                    closed_pnl=fill.closed_pnl,
                    close_fee=fill.fee,
                    net_pnl_approx=fill.closed_pnl - fill.fee,
                    sz=fill.sz,
                    notional=abs(fill.px * fill.sz),
                    liquidation=fill.liquidation,
                    direction=fill.direction,
                )
            )

        open_side = open_side_from_direction(fill.direction)
        if open_side:
            lots[(fill.coin, open_side)].append((fill.sz, fill.time_ms, fill.px))

    return closed


def consume_open_lots(lots: deque[tuple[float, int, float]], close_sz: float, close_time_ms: int) -> float | None:
    remaining = close_sz
    weighted_minutes = 0.0
    consumed = 0.0
    while lots and remaining > 0:
        lot_sz, open_time_ms, open_px = lots[0]
        use_sz = min(lot_sz, remaining)
        weighted_minutes += ((close_time_ms - open_time_ms) / 60_000) * use_sz
        consumed += use_sz
        remaining -= use_sz
        lot_sz -= use_sz
        if lot_sz <= 1e-12:
            lots.popleft()
        else:
            lots[0] = (lot_sz, open_time_ms, open_px)
    if consumed <= 0:
        return None
    return weighted_minutes / consumed


def open_side_from_direction(direction: str) -> str | None:
    if direction in {"Open Long", "Short > Long"}:
        return "LONG"
    if direction in {"Open Short", "Long > Short"}:
        return "SHORT"
    return None


def closed_side_from_direction(direction: str) -> str | None:
    if direction in {"Close Long", "Long > Short"}:
        return "LONG"
    if direction in {"Close Short", "Short > Long"}:
        return "SHORT"
    return None


def build_period_stats(fills: list[Fill], snapshot: AccountSnapshot) -> dict[str, Any]:
    closed_trades = build_closed_trades(fills)
    realized = sum(fill.closed_pnl for fill in fills)
    fees = sum(fill.fee for fill in fills)
    net = realized - fees
    wins = [trade for trade in closed_trades if trade.net_pnl_approx > 0]
    losses = [trade for trade in closed_trades if trade.net_pnl_approx < 0]
    gross_profit = sum(trade.net_pnl_approx for trade in wins)
    gross_loss = abs(sum(trade.net_pnl_approx for trade in losses))
    pf = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit > 0 else 0.0)

    return {
        "fills": fills,
        "closed_trades": closed_trades,
        "realized_pnl": realized,
        "fees": fees,
        "net_pnl": net,
        "unrealized_pnl": sum(pos.unrealized_pnl for pos in snapshot.positions),
        "fill_count": len(fills),
        "round_trips": len(closed_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0,
        "avg_win": gross_profit / len(wins) if wins else 0.0,
        "avg_loss": -(gross_loss / len(losses)) if losses else 0.0,
        "profit_factor": pf,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "side_summary": summarize_trades(closed_trades, lambda trade: trade.side),
        "coin_summary": summarize_trades(closed_trades, lambda trade: trade.coin),
        "duration_summary": summarize_trades(closed_trades, lambda trade: duration_bucket(trade.hold_minutes)),
        "size_summary": summarize_trades(
            closed_trades,
            lambda trade: size_bucket(account_ratio(trade.notional, snapshot.account_value)),
        ),
        "pattern_summary": summarize_patterns(closed_trades, snapshot.account_value),
    }


def summarize_trades(trades: list[ClosedTrade], key_fn: Any) -> list[dict[str, Any]]:
    groups: dict[str, list[ClosedTrade]] = defaultdict(list)
    for trade in trades:
        groups[str(key_fn(trade))].append(trade)
    rows = []
    for label, rows_trades in groups.items():
        wins = [trade for trade in rows_trades if trade.net_pnl_approx > 0]
        losses = [trade for trade in rows_trades if trade.net_pnl_approx < 0]
        net = sum(trade.net_pnl_approx for trade in rows_trades)
        holds = [trade.hold_minutes for trade in rows_trades if trade.hold_minutes is not None]
        rows.append(
            {
                "label": label,
                "wins": len(wins),
                "losses": len(losses),
                "trades": len(rows_trades),
                "net_pnl": net,
                "win_rate": (len(wins) / len(rows_trades) * 100) if rows_trades else 0,
                "avg_hold_minutes": sum(holds) / len(holds) if holds else None,
            }
        )
    rows.sort(key=lambda row: row["net_pnl"], reverse=True)
    return rows


def summarize_patterns(trades: list[ClosedTrade], account_value: float) -> list[dict[str, Any]]:
    groups: dict[str, list[ClosedTrade]] = defaultdict(list)
    for trade in trades:
        labels = [
            f"{trade.coin} {trade.side}",
            duration_bucket(trade.hold_minutes),
            size_bucket(account_ratio(trade.notional, account_value)),
        ]
        for label in labels:
            groups[label].append(trade)

    rows = []
    for label, grouped in groups.items():
        if len(grouped) < 2:
            continue
        wins = [trade for trade in grouped if trade.net_pnl_approx > 0]
        losses = [trade for trade in grouped if trade.net_pnl_approx < 0]
        rows.append(
            {
                "label": label,
                "wins": len(wins),
                "losses": len(losses),
                "trades": len(grouped),
                "net_pnl": sum(trade.net_pnl_approx for trade in grouped),
                "win_rate": len(wins) / len(grouped) * 100,
            }
        )
    rows.sort(key=lambda row: row["net_pnl"], reverse=True)
    return rows


def duration_bucket(minutes: float | None) -> str:
    if minutes is None:
        return "保有時間不明"
    if minutes < 5:
        return "5分未満"
    if minutes < 30:
        return "5-30分"
    if minutes < 120:
        return "30分-2時間"
    return "2時間以上"


def account_ratio(notional: float, account_value: float) -> float:
    if account_value <= 0:
        return 0.0
    return notional / account_value


def size_bucket(ratio: float) -> str:
    if ratio < 3:
        return "口座比0-3倍"
    if ratio < 6:
        return "口座比3-6倍"
    return "口座比6倍以上"


def evaluate_risk(snapshot: AccountSnapshot, fills_today: list[Fill], settings: Settings) -> dict[str, Any]:
    flags: list[dict[str, Any]] = []
    margin_usage_pct = (snapshot.total_margin_used / snapshot.account_value * 100) if snapshot.account_value > 0 else 0.0
    daily_realized = sum(fill.closed_pnl for fill in fills_today)
    daily_fees = sum(fill.fee for fill in fills_today)
    daily_net = daily_realized - daily_fees
    gross_profit = sum(max(fill.closed_pnl - fill.fee, 0) for fill in fills_today)
    liquidations = [fill for fill in fills_today if fill.liquidation]

    if margin_usage_pct >= settings.risk_max_margin_usage_pct and snapshot.positions:
        flags.append(flag("証拠金使用率90%以上", 15, f"証拠金使用率 {margin_usage_pct:.1f}%"))
    if snapshot.account_value > 0 and daily_net <= -(snapshot.account_value * settings.risk_daily_loss_pct / 100):
        flags.append(flag("日次実現損益が口座の-5%以上", 20, f"日次概算ネット {format_signed_usd(daily_net)}"))
    if liquidations:
        flags.append(flag("清算あり", 35, f"清算 {len(liquidations)}回"))
    if gross_profit > 0 and daily_fees / gross_profit >= 0.30:
        flags.append(flag("手数料が利益の30%以上", 8, f"手数料/粗利益 {daily_fees / gross_profit * 100:.1f}%"))
    if has_rapid_reversal_after_loss(fills_today):
        flags.append(flag("損失後の即反転", 12, "損失クローズ後60分以内に逆方向エントリー"))

    for pos in snapshot.positions:
        ratio = account_ratio(pos.position_value, snapshot.account_value)
        if pos.liquidation_distance_pct is not None and pos.liquidation_distance_pct < settings.risk_liquidation_distance_pct:
            flags.append(flag("清算距離5%未満", 25, f"{pos.coin} {pos.side} 清算距離 {pos.liquidation_distance_pct:.2f}%"))
        if ratio >= settings.risk_max_account_leverage:
            flags.append(flag("口座比6倍以上", 20, f"{pos.coin} {pos.side} 口座比 {ratio:.1f}倍"))
        if not has_protective_stop(pos, snapshot.open_orders):
            flags.append(flag("ストップなし", 20, f"{pos.coin} {pos.side} のreduceOnlyストップ注文なし"))

    severity = sum(item["severity"] for item in flags)
    reasons = [item["name"] for item in flags]
    position_key = "|".join(f"{pos.coin}:{pos.side}:{round(pos.szi, 8)}:{pos.entry_px}" for pos in snapshot.positions) or "flat"
    risk_key = f"{position_key}|{','.join(sorted(set(reasons)))}"
    return {
        "flags": flags,
        "severity": severity,
        "risk_key": risk_key,
        "daily_net": daily_net,
        "margin_usage_pct": margin_usage_pct,
    }


def flag(name: str, severity: float, detail: str) -> dict[str, Any]:
    return {"name": name, "severity": severity, "detail": detail}


def has_protective_stop(position: Position, orders: list[dict[str, Any]]) -> bool:
    expected_side = "S" if position.side == "LONG" else "B"
    for order in orders:
        if order.get("coin") != position.coin:
            continue
        if not order.get("reduceOnly"):
            continue
        if order.get("side") != expected_side:
            continue
        order_type = str(order.get("orderType") or "")
        if "Stop" in order_type and order.get("isTrigger"):
            return True
    return False


def has_rapid_reversal_after_loss(fills: list[Fill], window_minutes: int = 60) -> bool:
    sorted_fills = sorted(fills, key=lambda row: row.time_ms)
    for idx, fill in enumerate(sorted_fills):
        if closed_side_from_direction(fill.direction) is None or fill.closed_pnl >= 0:
            continue
        closed_side = closed_side_from_direction(fill.direction)
        for later in sorted_fills[idx + 1 :]:
            if later.time_ms - fill.time_ms > window_minutes * 60_000:
                break
            opened = open_side_from_direction(later.direction)
            if opened and opened != closed_side:
                return True
    return False


def score_daily(stats: dict[str, Any], risk: dict[str, Any], snapshot: AccountSnapshot) -> dict[str, Any]:
    account = max(snapshot.account_value, 1.0)
    net_pct = stats["net_pnl"] / account * 100
    result = clamp(25 + net_pct * 2.0, 0, 40)
    if stats["profit_factor"] >= 1.5:
        result += 5
    if stats["win_rate"] >= 55:
        result += 5
    result = clamp(result, 0, 50)

    risk_score = 50
    for item in risk["flags"]:
        name = item["name"]
        if name == "清算あり":
            risk_score -= 25
        elif name in {"清算距離5%未満", "ストップなし", "口座比6倍以上"}:
            risk_score -= 12
        elif name == "証拠金使用率90%以上":
            risk_score -= 10
        elif name == "損失後の即反転":
            risk_score -= 8
        else:
            risk_score -= 6
    risk_score = clamp(risk_score, 0, 50)
    total = int(round(result + risk_score))
    return {"total": total, "pnl_score": round(result, 1), "risk_score": round(risk_score, 1)}


def score_weekly(stats: dict[str, Any], risk: dict[str, Any], snapshot: AccountSnapshot) -> dict[str, Any]:
    account = max(snapshot.account_value, 1.0)
    net_pct = stats["net_pnl"] / account * 100
    pnl = clamp(20 + net_pct * 1.5, 0, 35)
    if stats["profit_factor"] >= 1.3:
        pnl += 5
    pnl = clamp(pnl, 0, 40)

    positive_patterns = [row for row in stats["pattern_summary"] if row["net_pnl"] > 0 and row["trades"] >= 2]
    negative_patterns = [row for row in stats["pattern_summary"] if row["net_pnl"] < 0 and row["trades"] >= 2]
    reproducibility = 15 + min(len(positive_patterns), 3) * 4 - min(len(negative_patterns), 3) * 2
    if stats["win_rate"] >= 55:
        reproducibility += 3
    reproducibility = clamp(reproducibility, 0, 30)

    risk_score = 30
    for item in risk["flags"]:
        if item["name"] == "清算あり":
            risk_score -= 12
        elif item["name"] in {"清算距離5%未満", "ストップなし", "口座比6倍以上", "証拠金使用率90%以上"}:
            risk_score -= 5
        else:
            risk_score -= 3
    risk_score = clamp(risk_score, 0, 30)
    total = int(round(pnl + reproducibility + risk_score))
    return {
        "total": total,
        "pnl_score": round(pnl, 1),
        "reproducibility_score": round(reproducibility, 1),
        "risk_score": round(risk_score, 1),
    }


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def format_signed_usd(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):.2f}"

