from typing import Any

from .models import AccountSnapshot, Fill, Position


def parse_snapshot(payload: dict[str, Any]) -> AccountSnapshot:
    state = payload["state"]
    mids = payload["mids"]
    orders = payload["orders"]
    margin = state.get("marginSummary", {})
    positions: list[Position] = []
    for item in state.get("assetPositions", []):
        raw = item.get("position", {})
        coin = str(raw.get("coin") or "")
        szi = _float(raw.get("szi"))
        if not coin or not szi:
            continue
        mid = _float(mids.get(coin)) if coin in mids else None
        liq = _float(raw.get("liquidationPx")) if raw.get("liquidationPx") else None
        distance = None
        if mid and liq:
            distance = ((mid - liq) / mid * 100) if szi > 0 else ((liq - mid) / mid * 100)
        leverage = raw.get("leverage") if isinstance(raw.get("leverage"), dict) else {}
        positions.append(
            Position(
                coin=coin,
                side="LONG" if szi > 0 else "SHORT",
                szi=szi,
                entry_px=_float(raw.get("entryPx")) if raw.get("entryPx") else None,
                mid_px=mid,
                unrealized_pnl=_float(raw.get("unrealizedPnl")),
                roe_pct=_float(raw.get("returnOnEquity")) * 100 if raw.get("returnOnEquity") is not None else None,
                leverage_type=leverage.get("type"),
                leverage_value=_float(leverage.get("value")) if leverage.get("value") is not None else None,
                liquidation_px=liq,
                liquidation_distance_pct=distance,
                margin_used=_float(raw.get("marginUsed")),
                position_value=_float(raw.get("positionValue")),
            )
        )

    return AccountSnapshot(
        time_ms=int(state.get("time") or 0),
        account_value=_float(margin.get("accountValue")),
        withdrawable=_float(state.get("withdrawable")),
        total_ntl_pos=_float(margin.get("totalNtlPos")),
        total_margin_used=_float(margin.get("totalMarginUsed")),
        positions=positions,
        open_orders=orders,
    )


def parse_fills(rows: list[dict[str, Any]]) -> list[Fill]:
    fills: list[Fill] = []
    for row in rows:
        fills.append(
            Fill(
                coin=str(row.get("coin") or ""),
                direction=str(row.get("dir") or ""),
                px=_float(row.get("px")),
                sz=_float(row.get("sz")),
                closed_pnl=_float(row.get("closedPnl")),
                fee=_float(row.get("fee")),
                time_ms=int(row.get("time") or 0),
                liquidation=bool(row.get("liquidation")),
                raw=row,
            )
        )
    fills.sort(key=lambda fill: fill.time_ms)
    return fills


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

