from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketPoint:
    ts: int
    price: float
    oi_usd: float
    volume_24h_usd: float
    funding_hourly: float | None = None
    volume_5m_usd: float | None = None


@dataclass
class AssetSnapshot:
    symbol: str
    exchanges: dict[str, MarketPoint] = field(default_factory=dict)


@dataclass
class Metrics:
    price: dict[str, float | None]
    oi: dict[str, float | None]
    volume: dict[str, float | None]
    funding: dict[str, float | None]
    funding_previous: float | None
    funding_zscore: float | None
    agreement_count: int
    agreement_total: int
    breakout_up: bool
    breakout_down: bool


@dataclass
class Detection:
    symbol: str
    direction: str
    level: int
    score: int
    metrics: Metrics
    reasons: list[str]
    next_conditions: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "direction": self.direction, "level": self.level, "score": self.score}
