from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from .logger import JST
from .models import AccountSnapshot, Fill

LEVELS = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "CRITICAL": 4}


def reconstruct_cycles(fills: list[Fill]) -> list[dict[str, Any]]:
    """API order is retained for timestamp ties; a flip closes one cycle and opens the next."""
    states: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for f in sorted(enumerate(fills), key=lambda item: (item[1].time_ms, item[0])):
        fill = f[1]
        before, after = fill.start_position, fill.end_position
        if abs(before) < 1e-12:
            states[fill.coin] = _new_cycle(fill, after)
            continue
        st = states.get(fill.coin) or _new_cycle(fill, before)
        same_direction_add = before * after > 0 and abs(after) > abs(before)
        partial_close = before * after > 0 and abs(after) < abs(before)
        if same_direction_add:
            old_abs, add = abs(before), abs(after - before)
            st["avg_entry"] = (st["avg_entry"] * old_abs + fill.px * add) / max(abs(after), 1e-12)
            st["number_of_adds"] += 1
        if partial_close:
            st["number_of_partial_closes"] += 1
        st["max_position_size"] = max(st["max_position_size"], abs(after))
        st["max_position_notional"] = max(st["max_position_notional"], abs(after) * fill.px)
        st["realized_pnl"] += fill.closed_pnl
        fee_for_old_cycle = fill.fee
        if before * after < 0:
            fee_for_old_cycle = fill.fee * abs(before) / max(fill.sz, 1e-12)
        st["fees"] += fee_for_old_cycle
        if abs(after) < 1e-12 or before * after < 0:
            st["closed_at"] = fill.time_ms
            st["duration_minutes"] = (fill.time_ms - st["opened_at"]) / 60_000
            out.append(_finish_cycle(st))
            states.pop(fill.coin, None)
            if before * after < 0:
                opening = _new_cycle(fill, after)
                opening["realized_pnl"] = 0.0
                opening["fees"] = fill.fee * abs(after) / max(fill.sz, 1e-12)
                states[fill.coin] = opening
        else:
            states[fill.coin] = st
    out.extend(_finish_cycle(st) for st in states.values())
    return sorted(out, key=lambda row: (row["opened_at"], row["coin"]))


def _new_cycle(fill: Fill, position: float) -> dict[str, Any]:
    direction = "LONG" if position > 0 else "SHORT"
    ident = hashlib.sha256(f"{fill.coin}|{direction}|{fill.time_ms}|{fill.tid}".encode()).hexdigest()[:24]
    return {"trade_id": ident, "coin": fill.coin, "direction": direction, "opened_at": fill.time_ms,
            "closed_at": None, "initial_entry": fill.px, "avg_entry": fill.px,
            "max_position_notional": abs(position) * fill.px, "max_position_size": abs(position),
            "realized_pnl": fill.closed_pnl, "fees": fill.fee, "duration_minutes": None,
            "number_of_adds": 0, "number_of_partial_closes": 0, "mae": None, "mfe": None,
            "behavior_json": "[]"}


def _finish_cycle(st: dict[str, Any]) -> dict[str, Any]:
    return dict(st)


def equity_stats(snapshot: AccountSnapshot, snapshot_rows: list[Any], start_ms: int, fills_today: list[Fill]) -> dict[str, float]:
    values = [float(row["account_value"]) for row in snapshot_rows if float(row["account_value"]) > 0]
    current = snapshot.account_value
    start = values[0] if values else current
    peak = max(values + [current]) if current > 0 else (max(values) if values else 0)
    low = min(values + [current]) if current > 0 else (min(values) if values else 0)
    dd = ((peak - current) / peak * 100) if peak > 0 else 0
    peak_profit = max(peak - start, 0)
    giveback = ((peak - current) / peak_profit * 100) if peak_profit > 0 else 0
    return {"start": start, "current": current, "peak": peak, "low": low, "drawdown_pct": dd,
            "giveback_pct": max(giveback, 0), "realized": sum(f.closed_pnl - f.fee for f in fills_today),
            "unrealized": sum(p.unrealized_pnl for p in snapshot.positions), "start_ms": start_ms}


def evaluate_behavior(snapshot: AccountSnapshot, fills: list[Fill], cycles: list[dict[str, Any]], equity: dict[str, float], settings: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    closed = [c for c in cycles if c["closed_at"] is not None]
    open_cycles = {c["coin"]: c for c in cycles if c["closed_at"] is None}
    last_closed = closed[-1] if closed else None
    if last_closed and last_closed["realized_pnl"] - last_closed["fees"] > 0:
        for c in open_cycles.values():
            if c["max_position_notional"] >= last_closed["max_position_notional"] * settings.size_up_multiplier:
                events.append(event("SIZE_UP_AFTER_WIN", c["coin"], "RED", c["opened_at"], "勝ち後の最大建玉が前回の1.5倍以上", {"multiple": c["max_position_notional"] / max(last_closed["max_position_notional"], 1e-9)}))
    ordered_cycles = sorted(cycles, key=lambda c: c["opened_at"])
    for prev in closed:
        net = prev["realized_pnl"] - prev["fees"]
        cur = next((c for c in ordered_cycles if c["coin"] == prev["coin"] and c["opened_at"] >= (prev["closed_at"] or 0)), None)
        if cur is None or cur["trade_id"] == prev["trade_id"]:
            continue
        mins = ((cur["opened_at"] - prev["closed_at"]) / 60_000) if prev["closed_at"] else 1e9
        if net < 0 and cur["coin"] == prev["coin"] and 0 <= mins <= settings.revenge_trade_minutes:
            level = "CRITICAL" if cur["direction"] != prev["direction"] else "RED"
            events.append(event("REVENGE_TRADE", cur["coin"], level, cur["opened_at"], f"損失終了から{mins:.1f}分で同一銘柄へ再エントリー", {"minutes": mins, "reversed": cur["direction"] != prev["direction"]}))
    for coin, rows in _coin_fills(fills).items():
        running_entry = None
        for f in rows:
            before, after = f.start_position, f.end_position
            if abs(before) < 1e-12:
                running_entry = f.px
                continue
            if before * after <= 0:
                running_entry = f.px if abs(after) > 1e-12 else None
                continue
            if abs(after) <= abs(before):
                continue
            entry = running_entry if running_entry is not None else f.px
            losing = (before > 0 and f.px < entry) or (before < 0 and f.px > entry)
            if losing:
                events.append(event("LOSS_AVERAGING", coin, "RED", f.time_ms, "含み損状態で同方向へ追加", {"position_increase": abs(after) / max(abs(before), 1e-9)}))
            else:
                pos = next((p for p in snapshot.positions if p.coin == coin), None)
                risk_pct = (abs(after) * f.px * .01 / snapshot.account_value * 100) if snapshot.account_value > 0 else 0
                if abs(after) >= abs(before) * 1.5 and pos and pos.unrealized_pnl >= snapshot.account_value * .10 and risk_pct >= 5:
                    events.append(event("PROFIT_PYRAMIDING", coin, "ORANGE", f.time_ms, "大きな含み益中に建玉を1.5倍以上へ追加", {"one_pct_equity_risk": risk_pct}))
            add = abs(after - before)
            running_entry = (entry * abs(before) + f.px * add) / max(abs(after), 1e-12)
    if equity["giveback_pct"] >= 30:
        events.append(event("DAILY_PROFIT_GIVEBACK", None, _threshold(equity["giveback_pct"], [(70,"RED"),(50,"ORANGE"),(30,"YELLOW")]), snapshot.time_ms, f"当日ピーク利益の{equity['giveback_pct']:.1f}%を吐き出し", equity))
    if equity["drawdown_pct"] >= 5:
        events.append(event("PEAK_DRAWDOWN", None, _threshold(equity["drawdown_pct"], [(15,"CRITICAL"),(10,"RED"),(8,"ORANGE"),(5,"YELLOW")]), snapshot.time_ms, f"当日ピークから-{equity['drawdown_pct']:.1f}%", equity))
    two_hours = settings.same_coin_window_minutes * 60_000
    for coin, rows in _coin_fills(fills).items():
        opens = [f for f in rows if abs(f.start_position) < 1e-12]
        if len(opens) >= settings.same_coin_trade_count and opens[-1].time_ms - opens[-settings.same_coin_trade_count].time_ms <= two_hours:
            events.append(event("SAME_COIN_OVERTRADE", coin, "ORANGE", opens[-1].time_ms, f"{settings.same_coin_window_minutes}分以内に{settings.same_coin_trade_count}回以上エントリー", {}))
    losses = 0
    for c in reversed(closed):
        if c["realized_pnl"] - c["fees"] < 0: losses += 1
        else: break
    if losses >= 2:
        events.append(event("CONSECUTIVE_LOSSES", None, "CRITICAL" if losses >= 4 else "RED" if losses >= 3 else "YELLOW", snapshot.time_ms, f"{losses}連敗", {"count": losses}))
    for p in snapshot.positions:
        if p.liquidation_distance_pct is not None and p.liquidation_distance_pct < 5:
            events.append(event("LIQUIDATION_TOO_CLOSE", p.coin, _threshold(5-p.liquidation_distance_pct, [(3.5,"CRITICAL"),(2,"RED"),(0,"ORANGE")]), snapshot.time_ms, f"清算価格まで{p.liquidation_distance_pct:.2f}%", {}))
        pct = (p.position_value * .01 / snapshot.account_value * 100) if snapshot.account_value > 0 else 0
        if pct >= 5:
            events.append(event("OVERSIZED_POSITION", p.coin, _threshold(pct, [(10,"CRITICAL"),(8,"RED"),(5,"ORANGE")]), snapshot.time_ms, f"価格1%変動で資産の{pct:.1f}%", {"one_pct_equity_risk": pct}))
    if equity["realized"] <= -settings.max_daily_loss:
        events.append(event("DAILY_LOSS_LIMIT", None, "CRITICAL", snapshot.time_ms, f"当日損失が${settings.max_daily_loss:.0f}上限を超過", equity))
    return _dedupe(events)


def aggregate_level(events: list[dict[str, Any]]) -> str:
    return max((e["level"] for e in events), key=lambda x: LEVELS[x], default="GREEN")


def event(kind: str, coin: str | None, level: str, time_ms: int, detail: str, metrics: dict[str, Any]) -> dict[str, Any]:
    bucket = time_ms // 60_000
    key = hashlib.sha256(f"{kind}|{coin}|{bucket}|{detail}".encode()).hexdigest()
    return {"event_key": key, "time_ms": time_ms, "risk_type": kind, "coin": coin, "level": level,
            "detail": detail, "metrics_json": json.dumps(metrics, ensure_ascii=False, sort_keys=True)}


def _threshold(value: float, levels: list[tuple[float, str]]) -> str:
    for threshold, level in levels:
        if value >= threshold: return level
    return "GREEN"


def _coin_fills(fills: list[Fill]) -> dict[str, list[Fill]]:
    out: dict[str, list[Fill]] = defaultdict(list)
    for f in fills: out[f.coin].append(f)
    return out


def _dedupe(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for e in events:
        key = (e["risk_type"], e["coin"], e["detail"])
        if key not in seen: seen.add(key); out.append(e)
    return out
