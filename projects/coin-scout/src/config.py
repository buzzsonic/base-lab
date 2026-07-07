from dataclasses import dataclass

from shared.envtools import ConfigError, read_bool, read_float, read_int, read_str


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    dry_run: bool
    # 監視対象フィルタ: Binance/Bybitの24h出来高がこの額(USD)以上の銘柄のみ
    min_cex_volume_usd: float
    # 出来高急増: 24h出来高が直近7日平均の何倍以上で発火するか
    volume_spike_ratio: float
    # 出来高急増と組み合わせる24h価格変動の最低ライン(%)
    price_move_min_pct: float
    # ファンディング偏り: 年率換算(%)の絶対値がこれ以上で発火
    funding_apr_alert_pct: float
    # OI急増: 前回スキャン比の増加率(%)がこれ以上で発火
    oi_change_alert_pct: float
    # ダイジェストに載せる最大銘柄数
    max_alerts: int
    # 出来高ベースライン計算に使う日数(当日を除く)
    baseline_days: int


def load_settings() -> Settings:
    webhook = read_str("DISCORD_WEBHOOK_URL")
    dry_run = read_bool("DRY_RUN", True)
    if not webhook and not dry_run:
        raise ConfigError("DISCORD_WEBHOOK_URL が未設定です(DRY_RUN=true なら省略可)。")

    return Settings(
        discord_webhook_url=webhook,
        dry_run=dry_run,
        min_cex_volume_usd=read_float("MIN_CEX_VOLUME_USD", 10_000_000),
        volume_spike_ratio=read_float("VOLUME_SPIKE_RATIO", 2.0),
        price_move_min_pct=read_float("PRICE_MOVE_MIN_PCT", 5.0),
        funding_apr_alert_pct=read_float("FUNDING_APR_ALERT_PCT", 30.0),
        oi_change_alert_pct=read_float("OI_CHANGE_ALERT_PCT", 20.0),
        max_alerts=read_int("MAX_ALERTS", 8),
        baseline_days=read_int("BASELINE_DAYS", 7),
    )
