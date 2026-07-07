from dataclasses import dataclass

from shared.envtools import ConfigError, read_bool, read_float, read_int, read_str

# 国内取引所で観測する銘柄(BTC/JPY等)。環境変数 SPREAD_LOGGER_COINS で増減可能。
DEFAULT_COINS = ("BTC", "ETH", "XRP", "SOL", "DOGE", "LTC")

# HL現物-パープのベーシスを見る対象。key=HL現物トークン名, value=対応するperpの銘柄名
HL_SPOT_BASIS_TARGETS = {
    "HYPE": "HYPE",
    "UBTC": "BTC",
    "UETH": "ETH",
    "USOL": "SOL",
}

FX_REFERENCE_URL = "https://open.er-api.com/v6/latest/USD"


@dataclass(frozen=True)
class Settings:
    discord_webhook_url: str
    dry_run: bool
    coins: tuple[str, ...]
    # 実効ドル円(国内mid ÷ HLパープ)が参照USDJPYからこの%以上乖離したら発火
    effective_jpy_dev_alert_pct: float
    # 国内取引所間クロス(bestbid > bestask)がこの%以上で発火
    domestic_cross_alert_pct: float
    # HLファンディング年率換算(%)の絶対値がこれ以上で発火
    funding_apr_alert_pct: float
    # HL現物-パープのベーシス(%)の絶対値がこれ以上で発火
    hl_basis_alert_pct: float
    # 同一アラート種別×銘柄のクールダウン(時間)
    alert_cooldown_hours: float


def _parse_coins(raw: str) -> tuple[str, ...]:
    coins = tuple(c.strip().upper() for c in raw.split(",") if c.strip())
    if not coins:
        raise ConfigError("SPREAD_LOGGER_COINS が空です。最低1銘柄を指定してください。")
    return coins


def load_settings() -> Settings:
    webhook = read_str("DISCORD_WEBHOOK_URL")
    dry_run = read_bool("DRY_RUN", True)
    if not webhook and not dry_run:
        raise ConfigError("DISCORD_WEBHOOK_URL が未設定です(DRY_RUN=true なら省略可)。")

    coins_raw = read_str("SPREAD_LOGGER_COINS", ",".join(DEFAULT_COINS))

    return Settings(
        discord_webhook_url=webhook,
        dry_run=dry_run,
        coins=_parse_coins(coins_raw),
        effective_jpy_dev_alert_pct=read_float("EFFECTIVE_JPY_DEV_ALERT_PCT", 0.4),
        domestic_cross_alert_pct=read_float("DOMESTIC_CROSS_ALERT_PCT", 0.3),
        funding_apr_alert_pct=read_float("FUNDING_APR_ALERT_PCT", 30.0),
        hl_basis_alert_pct=read_float("HL_BASIS_ALERT_PCT", 1.0),
        alert_cooldown_hours=read_float("ALERT_COOLDOWN_HOURS", 6.0),
    )
