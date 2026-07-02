import os
from dataclasses import dataclass
from pathlib import Path

from shared.envtools import (  # noqa: F401
    ConfigError,
    read_bool as _read_bool,
    read_float as _read_float,
    read_int as _read_int,
    read_str as _read_str,
)


DEFAULT_WALLET_ADDRESS = "0x5544C446E589fccB0d0B730e6289a22d967E6910"


@dataclass(frozen=True)
class Settings:
    wallet_address: str
    discord_webhook_url: str
    dry_run: bool
    daily_cutoff_hour_jst: int
    daily_notify_hour_jst: int
    daily_notify_minute_jst: int
    weekly_weekday_jst: int
    weekly_notify_hour_jst: int
    weekly_notify_minute_jst: int
    risk_cooldown_minutes: int
    risk_liquidation_distance_pct: float
    risk_max_account_leverage: float
    risk_max_margin_usage_pct: float
    risk_daily_loss_pct: float
    db_path: Path
    reports_dir: Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config(db_path: str | None = None, reports_dir: str | None = None, dry_run_override: bool | None = None) -> Settings:
    load_dotenv()

    wallet_address = _read_str("HYPERLIQUID_WALLET_ADDRESS", DEFAULT_WALLET_ADDRESS) or DEFAULT_WALLET_ADDRESS
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise ConfigError("HYPERLIQUID_WALLET_ADDRESS は 0x から始まる42文字のアドレスで指定してください。")

    dry_run = _read_bool("DRY_RUN", True) if dry_run_override is None else dry_run_override
    webhook_url = _read_str("DISCORD_WEBHOOK_URL")
    if not dry_run and not webhook_url:
        raise ConfigError("DISCORD_WEBHOOK_URL が未設定です。DRY_RUN=false の場合はGitHub Secretsまたは.envに設定してください。")

    return Settings(
        wallet_address=wallet_address,
        discord_webhook_url=webhook_url,
        dry_run=dry_run,
        daily_cutoff_hour_jst=_read_int("DAILY_REPORT_CUTOFF_HOUR_JST", 23),
        daily_notify_hour_jst=_read_int("DAILY_REPORT_NOTIFY_HOUR_JST", 23),
        daily_notify_minute_jst=_read_int("DAILY_REPORT_NOTIFY_MINUTE_JST", 30),
        weekly_weekday_jst=_read_int("WEEKLY_REPORT_WEEKDAY_JST", 6),
        weekly_notify_hour_jst=_read_int("WEEKLY_REPORT_NOTIFY_HOUR_JST", 22),
        weekly_notify_minute_jst=_read_int("WEEKLY_REPORT_NOTIFY_MINUTE_JST", 0),
        risk_cooldown_minutes=_read_int("RISK_COOLDOWN_MINUTES", 60),
        risk_liquidation_distance_pct=_read_float("RISK_LIQUIDATION_DISTANCE_PCT", 5),
        risk_max_account_leverage=_read_float("RISK_MAX_ACCOUNT_LEVERAGE", 6),
        risk_max_margin_usage_pct=_read_float("RISK_MAX_MARGIN_USAGE_PCT", 90),
        risk_daily_loss_pct=_read_float("RISK_DAILY_LOSS_PCT", 5),
        db_path=Path(db_path or _read_str("WALLET_REPORT_DB_PATH", ".state/wallet_report.sqlite")),
        reports_dir=Path(reports_dir or _read_str("WALLET_REPORTS_DIR", "reports")),
    )
