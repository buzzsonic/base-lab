import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    coin: str
    discord_webhook_url: str | None
    dry_run: bool
    notify_heartbeat: bool


def load_settings() -> Settings:
    return Settings(
        coin=os.environ.get("COIN", "HYPE").strip().upper() or "HYPE",
        discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL"),
        dry_run=_env_bool("DRY_RUN", False),
        notify_heartbeat=_env_bool("NOTIFY_HEARTBEAT", False),
    )
