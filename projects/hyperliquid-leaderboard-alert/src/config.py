import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    alert_mode: str
    leaderboard_limit: int
    target_side: str
    min_abs_position_usd: float
    min_position_change_usd: float
    dry_run: bool


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
    if not webhook_url:
        raise ConfigError("DISCORD_WEBHOOK_URL が未設定です。GitHub Secrets または .env に設定してください。")

    alert_mode = _read_str("ALERT_MODE", "leaderboard").lower()
    if alert_mode != "leaderboard":
        raise ConfigError("ALERT_MODE は初期版では leaderboard のみ対応しています。")

    leaderboard_limit = _read_int("LEADERBOARD_LIMIT", 100)
    if leaderboard_limit <= 0:
        raise ConfigError("LEADERBOARD_LIMIT は1以上で指定してください。")

    target_side = _read_str("TARGET_SIDE", "both").lower()
    if target_side not in {"both", "long", "short"}:
        raise ConfigError("TARGET_SIDE は both, long, short のいずれかで指定してください。")

    min_abs_position_usd = _read_float("MIN_ABS_POSITION_USD", 10000)
    if min_abs_position_usd < 0:
        raise ConfigError("MIN_ABS_POSITION_USD は0以上で指定してください。")

    min_position_change_usd = _read_float("MIN_POSITION_CHANGE_USD", 5000)
    if min_position_change_usd < 0:
        raise ConfigError("MIN_POSITION_CHANGE_USD は0以上で指定してください。")

    return Settings(
        discord_webhook_url=webhook_url,
        alert_mode=alert_mode,
        leaderboard_limit=leaderboard_limit,
        target_side=target_side,
        min_abs_position_usd=min_abs_position_usd,
        min_position_change_usd=min_position_change_usd,
        dry_run=_read_bool("DRY_RUN", False),
    )
