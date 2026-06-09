import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    coin: str
    discord_webhook_url: str | None
    dry_run: bool
    notify_heartbeat: bool
    notify_empty: bool
    empty_notification_interval_minutes: int


def load_settings() -> Settings:
    return Settings(
        coin=os.environ.get("COIN", "HYPE").strip().upper() or "HYPE",
        discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL"),
        dry_run=_env_bool("DRY_RUN", False),
        notify_heartbeat=_env_bool("NOTIFY_HEARTBEAT", False),
        notify_empty=_env_bool("NOTIFY_EMPTY", False),
        empty_notification_interval_minutes=max(_env_int("EMPTY_NOTIFICATION_INTERVAL_MINUTES", 60), 1),
    )
