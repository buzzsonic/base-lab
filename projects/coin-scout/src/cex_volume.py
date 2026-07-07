"""Binance/Bybitの24h出来高(USD)を取得し、ベース通貨ごとに集約する。

Hyperliquidの銘柄名との対応:
- HLの "kPEPE" 等の1000倍銘柄はベース通貨 "PEPE" として扱う
- CEX側の "1000PEPEUSDT" 等もベース通貨 "PEPE" に正規化する
- 出来高はUSD建てクオート出来高なのでスケール補正は不要
"""

from typing import Any

import requests

# api.binance.com は米国IP(GitHub Actionsランナー等)を451でブロックするため、
# 地域制限のない公式市場データミラー data-api.binance.vision を使う
BINANCE_SPOT_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"
BYBIT_LINEAR_URL = "https://api.bybit.com/v5/market/tickers?category=linear"

QUOTE_CURRENCIES = ("USDT", "USDC")
TIMEOUT_SECONDS = 20


def normalize_base(symbol: str) -> str:
    """CEXシンボル/HL銘柄名をベース通貨名に正規化する(例: 1000PEPE→PEPE, kPEPE→PEPE)。"""
    base = symbol.upper()
    if base.startswith("1000") and len(base) > 4:
        base = base[4:]
        # 1M系(1000000MOG等)にも対応
        if base.startswith("000") and len(base) > 3:
            base = base[3:]
    return base


def normalize_hl_coin(coin: str) -> str:
    if coin.startswith("k") and len(coin) > 1 and coin[1:].isupper():
        return coin[1:].upper()
    return coin.upper()


def _split_quote(symbol: str) -> tuple[str, str] | None:
    for quote in QUOTE_CURRENCIES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return None


def _merge_max(volumes: dict[str, float], base: str, volume_usd: float) -> None:
    """同一ベース通貨は取引所・ペア間で最大値を採用する(合算すると二重計上になるため)。"""
    if volume_usd > volumes.get(base, 0.0):
        volumes[base] = volume_usd


def _fetch_json(url: str, logger: Any) -> Any | None:
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"CEX出来高の取得に失敗: {url} / {exc}")
        return None


def fetch_binance_volumes(logger: Any) -> dict[str, float]:
    """Binance(現物+USDT-M先物)の24h出来高(USD)をベース通貨→出来高で返す。"""
    volumes: dict[str, float] = {}
    for url in (BINANCE_SPOT_URL, BINANCE_FUTURES_URL):
        data = _fetch_json(url, logger)
        if not isinstance(data, list):
            continue
        for ticker in data:
            if not isinstance(ticker, dict):
                continue
            parsed = _split_quote(str(ticker.get("symbol", "")))
            if parsed is None:
                continue
            base_raw, _ = parsed
            try:
                quote_volume = float(ticker.get("quoteVolume", 0.0))
            except (TypeError, ValueError):
                continue
            _merge_max(volumes, normalize_base(base_raw), quote_volume)
    return volumes


def fetch_bybit_volumes(logger: Any) -> dict[str, float]:
    """Bybit(USDT無期限)の24h出来高(USD)をベース通貨→出来高で返す。"""
    volumes: dict[str, float] = {}
    data = _fetch_json(BYBIT_LINEAR_URL, logger)
    if not isinstance(data, dict):
        return volumes
    tickers = (data.get("result") or {}).get("list")
    if not isinstance(tickers, list):
        logger.warning("Bybit応答の形式が不正です。")
        return volumes
    for ticker in tickers:
        if not isinstance(ticker, dict):
            continue
        parsed = _split_quote(str(ticker.get("symbol", "")))
        if parsed is None:
            continue
        base_raw, _ = parsed
        try:
            turnover = float(ticker.get("turnover24h", 0.0))
        except (TypeError, ValueError):
            continue
        _merge_max(volumes, normalize_base(base_raw), turnover)
    return volumes


def fetch_cex_volumes(logger: Any) -> dict[str, dict[str, float]]:
    """ベース通貨 → {"binance": vol, "bybit": vol} を返す。取れなかった取引所のキーは持たない。"""
    result: dict[str, dict[str, float]] = {}
    binance = fetch_binance_volumes(logger)
    bybit = fetch_bybit_volumes(logger)
    logger.info(f"CEX出来高取得: Binance {len(binance)}銘柄, Bybit {len(bybit)}銘柄")
    for base, volume in binance.items():
        result.setdefault(base, {})["binance"] = volume
    for base, volume in bybit.items():
        result.setdefault(base, {})["bybit"] = volume
    return result


def max_cex_volume(entry: dict[str, float] | None) -> float:
    if not entry:
        return 0.0
    return max(entry.values())
