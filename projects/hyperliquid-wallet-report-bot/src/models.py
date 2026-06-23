from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Position:
    coin: str
    side: str
    szi: float
    entry_px: float | None
    mid_px: float | None
    unrealized_pnl: float
    roe_pct: float | None
    leverage_type: str | None
    leverage_value: float | None
    liquidation_px: float | None
    liquidation_distance_pct: float | None
    margin_used: float
    position_value: float


@dataclass(frozen=True)
class Fill:
    coin: str
    direction: str
    px: float
    sz: float
    closed_pnl: float
    fee: float
    time_ms: int
    liquidation: bool
    raw: dict[str, Any]


@dataclass(frozen=True)
class AccountSnapshot:
    time_ms: int
    account_value: float
    withdrawable: float
    total_ntl_pos: float
    total_margin_used: float
    positions: list[Position]
    open_orders: list[dict[str, Any]]


@dataclass(frozen=True)
class ClosedTrade:
    coin: str
    side: str
    close_time_ms: int
    hold_minutes: float | None
    closed_pnl: float
    close_fee: float
    net_pnl_approx: float
    sz: float
    notional: float
    liquidation: bool
    direction: str

