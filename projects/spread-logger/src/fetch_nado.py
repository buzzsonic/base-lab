"""Nado(Ink L2のCLOB DEX)の公開APIから、パープの板・オラクル価格・FR・OIを取得する。

Variationalと同じくポイ活勢のフローでFRが歪みうるベニュー。HLとの差分を貯めるために取得する。

APIの構成(いずれも無認証で叩ける):
  - gateway `?type=symbols`      … シンボル名 → product_id の対応表
  - gateway `?type=all_products` … perp_productsに oracle_price_x18 と state.open_interest
  - gateway `?type=market_price&product_id=N` … 板の best bid/ask (x18)
  - archive  POST {"funding_rate": {"product_id": N}} … funding_rate_x18

ハマりどころ:
  1. **Accept-Encoding が必須**。gzip/br/deflate のいずれかを含めないと 403 で
     `{"reason": "Invalid compression headers", "block": true}` が返る。requestsは既定で
     gzipを送るが、意図を明示するため下でヘッダを固定している。
  2. **funding_rate_x18 は「24時間レート」**。公式ドキュメントに
     「APIが返す funding_rate は 8時間レート F の3倍 = 1日で積み上がる総額に相当する」
     と明記されている(実際の決済は毎時 F/8)。よって APR% = 日次レート × 365 × 100。
     時間レートとして扱うと24倍に膨れるので注意。
  3. 板と建玉は product_id 単位でしか引けないため、銘柄数ぶんリクエストが増える
     (既定7銘柄で 2 + 7×2 = 16リクエスト/実行)。15分間隔なら許容範囲。
"""

from typing import Any

import requests

TIMEOUT_SECONDS = 20

NADO_GATEWAY_URL = "https://gateway.prod.nado.xyz/v1/query"
NADO_ARCHIVE_URL = "https://archive.prod.nado.xyz/v1"

# 圧縮ヘッダが無いとgatewayが403で弾く(モジュール冒頭の注記1)
HEADERS = {"Accept-Encoding": "gzip, deflate"}

X18 = 10**18
DAYS_PER_YEAR = 365


def _from_x18(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value) / X18
    except (TypeError, ValueError):
        return None


def _gateway_query(params: dict[str, Any], logger: Any) -> dict[str, Any] | None:
    try:
        response = requests.get(NADO_GATEWAY_URL, params=params, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"Nado: gateway {params.get('type')} の取得に失敗: {exc}")
        return None
    if payload.get("status") != "success":
        logger.warning(f"Nado: gateway {params.get('type')} が success を返しませんでした: {payload}")
        return None
    return payload.get("data")


def _fetch_product_ids(coins: tuple[str, ...], logger: Any) -> dict[str, int]:
    """コイン名 → product_id。銘柄名は "BTC-PERP" 形式。"""
    data = _gateway_query({"type": "symbols"}, logger)
    if not data:
        return {}

    symbols = data.get("symbols") or {}
    result: dict[str, int] = {}
    for coin in coins:
        entry = symbols.get(f"{coin.upper()}-PERP")
        if entry is None or entry.get("type") != "perp":
            logger.warning(f"Nado: {coin} のパープが見つかりません(未上場)")
            continue
        product_id = entry.get("product_id")
        if isinstance(product_id, int):
            result[coin] = product_id
    return result


def _fetch_product_states(logger: Any) -> dict[int, dict[str, float | None]]:
    """product_id → {"oracle": .., "open_interest": ..}。"""
    data = _gateway_query({"type": "all_products"}, logger)
    if not data:
        return {}

    result: dict[int, dict[str, float | None]] = {}
    for product in data.get("perp_products") or []:
        product_id = product.get("product_id")
        if not isinstance(product_id, int):
            continue
        state = product.get("state") or {}
        result[product_id] = {
            "oracle": _from_x18(product.get("oracle_price_x18")),
            "open_interest": _from_x18(state.get("open_interest")),
        }
    return result


def _fetch_market_price(product_id: int, logger: Any) -> tuple[float | None, float | None]:
    data = _gateway_query({"type": "market_price", "product_id": product_id}, logger)
    if not data:
        return None, None
    return _from_x18(data.get("bid_x18")), _from_x18(data.get("ask_x18"))


def _fetch_funding_daily(product_id: int, logger: Any) -> float | None:
    """日次(24時間)ファンディングレートを小数で返す。"""
    try:
        response = requests.post(
            NADO_ARCHIVE_URL,
            json={"funding_rate": {"product_id": product_id}},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"Nado: product_id={product_id} のFR取得に失敗: {exc}")
        return None
    return _from_x18(payload.get("funding_rate_x18"))


def fetch_nado_perps(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float | None]]:
    """指定銘柄のNadoパープ情報を コイン名→{...} で返す。

    シンボル表が引けなければ空dictを返す。個別銘柄の欠測は警告のうえスキップする。
    """
    product_ids = _fetch_product_ids(coins, logger)
    if not product_ids:
        return {}

    states = _fetch_product_states(logger)

    result: dict[str, dict[str, float | None]] = {}
    for coin, product_id in product_ids.items():
        bid, ask = _fetch_market_price(product_id, logger)
        funding_daily = _fetch_funding_daily(product_id, logger)
        state = states.get(product_id, {})

        mid = None
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2

        result[coin] = {
            "product_id": product_id,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "oracle": state.get("oracle"),
            "open_interest": state.get("open_interest"),
            "funding_daily": funding_daily,
            # funding_rate_x18 は24時間レート(モジュール冒頭の注記2)
            "funding_apr_pct": None if funding_daily is None else funding_daily * DAYS_PER_YEAR * 100,
        }

    return result
