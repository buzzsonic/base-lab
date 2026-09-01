import os
from dataclasses import dataclass


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    webhook: str | None = os.getenv("DISCORD_WEBHOOK_URL")
    debug: bool = _bool("DEBUG")
    min_volume: float = _float("MIN_24H_VOLUME_USD", 1_000_000)
    funding: tuple[float, ...] = (_float("LEVEL1_FUNDING", -.0003), _float("LEVEL2_FUNDING", -.0008), _float("LEVEL3_FUNDING", -.0015), _float("LEVEL4_FUNDING", -.0030))
    oi_1h: tuple[float, ...] = (_float("LEVEL1_OI_1H", .05), _float("LEVEL2_OI_1H", .10), _float("LEVEL3_OI_1H", .12), _float("LEVEL4_OI_1H", .50))
    volume: tuple[float, ...] = (_float("LEVEL1_VOLUME_MULTIPLIER", 1.3), _float("LEVEL2_VOLUME_MULTIPLIER", 1.5), _float("LEVEL3_VOLUME_MULTIPLIER", 2.5), _float("LEVEL4_VOLUME_MULTIPLIER", 3.0))
    renotify_hours: float = _float("RENOTIFY_HOURS", 6)
    renotify_score_delta: int = int(_float("RENOTIFY_SCORE_DELTA", 15))
    history_days: int = int(_float("HISTORY_DAYS", 14))
    max_symbols: int = int(_float("MAX_SYMBOLS", 0))
