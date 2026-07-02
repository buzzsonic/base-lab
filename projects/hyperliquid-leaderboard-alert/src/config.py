from dataclasses import dataclass

from dotenv import load_dotenv

from shared.envtools import (  # noqa: F401
    ConfigError,
    read_bool as _read_bool,
    read_float as _read_float,
    read_int as _read_int,
    read_str as _read_str,
)


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    alert_mode: str
    leaderboard_limit: int
    target_side: str
    min_abs_position_usd: float
    min_position_change_usd: float
    dry_run: bool


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

    min_position_change_usd = _read_float("MIN_POSITION_CHANGE_USD", 500000)
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
