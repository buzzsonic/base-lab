import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    leaderboard_limit: int
    target_symbols: tuple[str, ...]
    near_band_pct: float
    watch_band_pct: float
    min_near_change_usd: float
    min_watch_change_usd: float
    min_active_usd: float
    liquidation_band_pct: float
    liquidation_bucket_pct: float
    min_liquidation_usd: float
    min_oi_delta_usd: float
    max_liquidation_levels: int
    request_sleep_seconds: float
    notify_empty: bool
    dry_run: bool
    state_path: Path


def _read_str(name: str, default: str | None = None) -> str:
    raw = os.environ.get(name, default)
    return "" if raw is None else str(raw).strip()


def _read_int(name: str, default: int) -> int:
    raw = _read_str(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} は整数で指定してください。現在値: {raw!r}") from exc


def _read_float(name: str, default: float) -> float:
    raw = _read_str(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} は数値で指定してください。現在値: {raw!r}") from exc


def _read_bool(name: str, default: bool) -> bool:
    raw = _read_str(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"{name} は true または false で指定してください。現在値: {raw!r}")


def load_config() -> Settings:
    load_dotenv()

    webhook_url = _read_str("DISCORD_WEBHOOK_URL")
    dry_run = _read_bool("DRY_RUN", False)
    if not webhook_url and not dry_run:
        raise ConfigError("DISCORD_WEBHOOK_URL が未設定です。GitHub Secrets または .env に設定してください。")

    raw_targets = _read_str("TARGET_SYMBOLS", "LIT,HYPE,ZEC,NEAR")
    targets: list[str] = []
    seen_targets: set[str] = set()
    for item in raw_targets.split(","):
        target = item.strip().upper()
        if target and target not in seen_targets:
            targets.append(target)
            seen_targets.add(target)
    target_symbols = tuple(targets)
    if not target_symbols:
        raise ConfigError("TARGET_SYMBOLS は1つ以上指定してください。例: HYPE,ZEC")

    leaderboard_limit = _read_int("LEADERBOARD_LIMIT", 100)
    if leaderboard_limit <= 0:
        raise ConfigError("LEADERBOARD_LIMIT は1以上で指定してください。")

    near_band_pct = _read_float("NEAR_BAND_PCT", 1.0)
    watch_band_pct = _read_float("WATCH_BAND_PCT", 3.0)
    if near_band_pct <= 0 or watch_band_pct <= 0 or near_band_pct > watch_band_pct:
        raise ConfigError("NEAR_BAND_PCT と WATCH_BAND_PCT は 0 < near <= watch で指定してください。")

    min_near_change_usd = _read_float("MIN_NEAR_CHANGE_USD", 500000)
    min_watch_change_usd = _read_float("MIN_WATCH_CHANGE_USD", 1000000)
    min_active_usd = _read_float("MIN_ACTIVE_USD", 500000)
    if min_near_change_usd < 0 or min_watch_change_usd < 0 or min_active_usd < 0:
        raise ConfigError("閾値USDは0以上で指定してください。")

    liquidation_band_pct = _read_float("LIQUIDATION_BAND_PCT", 5.0)
    liquidation_bucket_pct = _read_float("LIQUIDATION_BUCKET_PCT", 0.5)
    min_liquidation_usd = _read_float("MIN_LIQUIDATION_USD", 100000)
    min_oi_delta_usd = _read_float("MIN_OI_DELTA_USD", 1000000)
    max_liquidation_levels = _read_int("MAX_LIQUIDATION_LEVELS", 2)
    if liquidation_band_pct <= 0:
        raise ConfigError("LIQUIDATION_BAND_PCT は0より大きい数値で指定してください。")
    if liquidation_bucket_pct <= 0:
        raise ConfigError("LIQUIDATION_BUCKET_PCT は0より大きい数値で指定してください。")
    if min_liquidation_usd < 0 or min_oi_delta_usd < 0:
        raise ConfigError("MIN_LIQUIDATION_USD と MIN_OI_DELTA_USD は0以上で指定してください。")
    if max_liquidation_levels <= 0:
        raise ConfigError("MAX_LIQUIDATION_LEVELS は1以上で指定してください。")

    state_path = Path(_read_str("STATE_PATH", ".state/hype_zec_order_snapshot.json"))

    return Settings(
        discord_webhook_url=webhook_url,
        leaderboard_limit=leaderboard_limit,
        target_symbols=target_symbols,
        near_band_pct=near_band_pct,
        watch_band_pct=watch_band_pct,
        min_near_change_usd=min_near_change_usd,
        min_watch_change_usd=min_watch_change_usd,
        min_active_usd=min_active_usd,
        liquidation_band_pct=liquidation_band_pct,
        liquidation_bucket_pct=liquidation_bucket_pct,
        min_liquidation_usd=min_liquidation_usd,
        min_oi_delta_usd=min_oi_delta_usd,
        max_liquidation_levels=max_liquidation_levels,
        request_sleep_seconds=_read_float("REQUEST_SLEEP_SECONDS", 0.12),
        notify_empty=_read_bool("NOTIFY_EMPTY", False),
        dry_run=dry_run,
        state_path=state_path,
    )
