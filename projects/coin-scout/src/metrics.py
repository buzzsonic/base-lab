"""実測時刻だけを使う特徴量。補間せず、欠測はNoneと理由で保持する。"""

from __future__ import annotations

import math
import statistics
from typing import Any


def nearest_prior(
    history: list[dict[str, Any]], now_ms: int, minutes: int, tolerance_minutes: int
) -> tuple[dict[str, Any] | None, float | None]:
    target = now_ms - minutes * 60_000
    candidates = [row for row in history if isinstance(row.get("observed_at_ms"), int)]
    if not candidates:
        return None, None
    row = min(candidates, key=lambda item: abs(item["observed_at_ms"] - target))
    error_minutes = abs(row["observed_at_ms"] - target) / 60_000
    if error_minutes > tolerance_minutes:
        return None, error_minutes
    return row, error_minutes


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def robust_funding_anomaly(current: float | None, hourly_history: list[float]) -> dict[str, Any]:
    """過去値だけのmedian/MAD。MAD=0時はz値を出さない。"""
    clean = [float(value) for value in hourly_history if math.isfinite(float(value))]
    result = {"reference_samples": len(clean), "median": None, "mad": None, "robust_z": None}
    if current is None or len(clean) < 24:
        return result
    median = statistics.median(clean)
    mad = statistics.median(abs(value - median) for value in clean)
    result.update({"median": median, "mad": mad})
    if mad > 0:
        result["robust_z"] = 0.6745 * (current - median) / mad
    return result


def trade_imbalance(trades: list[dict[str, Any]], start_ms: int, end_ms: int) -> dict[str, Any]:
    """HL recentTradesのB=買い手主導、A=売り手主導として直接約定のみ集計。"""
    valid = []; returned_times=[]
    for trade in trades:
        try:
            ts = int(trade["time"])
            side = str(trade["side"])
            size = float(trade["sz"])
            price = float(trade["px"])
        except (KeyError, TypeError, ValueError):
            continue
        returned_times.append(ts)
        if start_ms <= ts <= end_ms and side in {"A", "B"}:
            valid.append((ts, side, size, price))
    buy = sum(size * price for _, side, size, price in valid if side == "B")
    sell = sum(size * price for _, side, size, price in valid if side == "A")
    total = buy + sell
    earliest = min(returned_times, default=None)
    # recentTradesは件数上限がある。区間開始まで遡れていなければ完全区間とは扱わない。
    complete = earliest is not None and earliest <= start_ms
    return {
        "buy_taker_notional_usd": buy,
        "sell_taker_notional_usd": sell,
        "delta_notional_usd": buy - sell,
        "normalized_imbalance": (buy - sell) / total if total > 0 else None,
        "trade_count": len(valid),
        "earliest_trade_ms": earliest,
        "coverage_complete": complete,
        "coverage_reason": None if complete else "recentTradesが区間開始まで到達せず部分取得",
    }


def high_low_position(candles: list[dict[str, Any]], price: float | None, now_ms: int) -> dict[str, Any]:
    rows = []
    for candle in candles:
        try:
            rows.append((int(candle["t"]), float(candle["h"]), float(candle["l"]), float(candle["c"])))
        except (KeyError, TypeError, ValueError):
            continue
    if price is None or not rows:
        return {"from_high_pct": None, "from_low_pct": None, "high_age_minutes": None, "low_age_minutes": None, "atr_return_ratio": None}
    high_row = max(rows, key=lambda row: row[1]); low_row = min(rows, key=lambda row: row[2])
    true_ranges = [(high-low)/close*100 for _, high, low, close in rows if close > 0]
    atr_pct = statistics.mean(true_ranges) if true_ranges else None
    from_high = (price / high_row[1] - 1) * 100
    from_low = (price / low_row[2] - 1) * 100
    return {
        "from_high_pct": from_high,
        "from_low_pct": from_low,
        "high_age_minutes": max(0, (now_ms-high_row[0])/60_000),
        "low_age_minutes": max(0, (now_ms-low_row[0])/60_000),
        "atr_pct_1m_mean": atr_pct,
        "atr_return_ratio": abs(from_high)/atr_pct if atr_pct else None,
    }


def high_low_from_snapshots(history: list[dict[str, Any]], price: float | None, now_ms: int) -> dict[str, Any]:
    """直近1時間の実測snapshot経路。OHLCではないためATRとは呼ばない。"""
    rows=[row for row in history if now_ms-60*60_000 <= row.get("observed_at_ms",0) <= now_ms and row.get("price") is not None]
    rows=sorted(rows,key=lambda row:row["observed_at_ms"])
    if price is not None:rows=rows+[{"observed_at_ms":now_ms,"price":price}]
    if len(rows)<2:return {"from_high_pct":None,"from_low_pct":None,"high_age_minutes":None,"low_age_minutes":None,"observed_mean_abs_change_pct":None,"retrace_to_normal_move_ratio":None,"path_samples":len(rows)}
    high=max(rows,key=lambda row:row["price"]);low=min(rows,key=lambda row:row["price"])
    changes=[abs((b["price"]/a["price"]-1)*100) for a,b in zip(rows,rows[1:]) if a["price"]]
    normal=statistics.mean(changes) if changes else None
    from_high=(price/high["price"]-1)*100;from_low=(price/low["price"]-1)*100
    return {"from_high_pct":from_high,"from_low_pct":from_low,"high_age_minutes":max(0,(now_ms-high["observed_at_ms"])/60_000),"low_age_minutes":max(0,(now_ms-low["observed_at_ms"])/60_000),"observed_mean_abs_change_pct":normal,"retrace_to_normal_move_ratio":abs(from_high)/normal if normal else None,"path_samples":len(rows)}


def anomaly_score(features: dict[str, Any]) -> tuple[float | None, list[str]]:
    """方向期待値ではない0-100異常度。欠測は0点でなく分母から除外する。"""
    components: list[tuple[str, float | None, float]] = []
    price_moves = [abs(features.get(f"price_change_{w}_pct")) for w in ("5m", "15m", "1h") if features.get(f"price_change_{w}_pct") is not None]
    oi_moves = [abs(features.get(f"oi_qty_change_{w}_pct")) for w in ("5m", "15m", "1h") if features.get(f"oi_qty_change_{w}_pct") is not None]
    components.append(("price", min(100, max(price_moves, default=0)/5*100) if price_moves else None, 0.30))
    components.append(("oi_qty", min(100, max(oi_moves, default=0)/10*100) if oi_moves else None, 0.25))
    funding_z = features.get("funding_robust_z")
    components.append(("funding", min(100, abs(funding_z)/5*100) if funding_z is not None else None, 0.15))
    trade = features.get("trade_imbalance_5m") or {}
    components.append(("taker_flow", min(100, abs(trade.get("normalized_imbalance"))/0.6*100) if trade.get("coverage_complete") and trade.get("normalized_imbalance") is not None else None, 0.20))
    # 高安値位置は価格変化と相関が強いため異常度へ重ねず、通知の文脈にだけ使う。
    available = [(name, score, weight) for name, score, weight in components if score is not None]
    if not available:
        return None, []
    denominator = sum(weight for _, _, weight in available)
    score = sum(score * weight for _, score, weight in available) / denominator
    return round(score, 1), [name for name, _, _ in available]
