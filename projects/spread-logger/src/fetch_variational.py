"""Variational Omni の公開統計APIから、パープのmark/FR/OI/板スプレッドを取得する。

ポイ活(ポイントファーミング)勢は「ボリュームを作る」のが目的で価格に無関心なため、
FRが恒常的に歪む可能性がある。その歪みをHLと突き合わせて検証するためのデータ取得。

エンドポイントは公開・無認証の1本のみ(GET /metadata/stats)で、全listingが1レスポンスに載る。
レート制限はIPあたり10req/10秒なので、15分毎の1リクエストは問題にならない。

funding_rate の単位について(2026-08-03 実機検証):
  公式ドキュメントは "funding rates are decimals (multiply by 100 for percentage)" としか
  書いておらず、どの期間のレートかを明示していない。526マーケットの実測値を調べたところ、
  302本がちょうど 0.1095 に張り付いていた。これは業界標準の金利成分 0.01%/8h を年率換算した
  値(0.0001 × 3 × 365 = 0.1095)と一致する。したがって funding_rate は「年率の小数」であり、
  APR% = funding_rate × 100 として扱う。
  (8時間レートなら基準値は 0.0001、日次レートなら 0.0003 になるはずで、どちらも観測と合わない)
  この前提が崩れるとFR比較が丸ごと無意味になるので、値の分布が変わっていないか時々確認すること。
"""

from typing import Any

import requests

TIMEOUT_SECONDS = 20

VARIATIONAL_STATS_URL = "https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/stats"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_variational_perps(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float | None]]:
    """指定銘柄のVariationalパープ情報を コイン名→{...} で返す。

    取得に失敗した場合は空dictを返す(他ベニューの記録は続行させる)。
    未上場銘柄は警告を出してスキップする。
    """
    try:
        response = requests.get(VARIATIONAL_STATS_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error(f"Variational: 統計の取得に失敗: {exc}")
        return {}

    listings = payload.get("listings")
    if not isinstance(listings, list):
        logger.error("Variational: レスポンスに listings 配列がありません")
        return {}

    by_ticker = {entry.get("ticker"): entry for entry in listings if isinstance(entry, dict)}

    result: dict[str, dict[str, float | None]] = {}
    for coin in coins:
        entry = by_ticker.get(coin.upper())
        if entry is None:
            logger.warning(f"Variational: {coin} が見つかりません(未上場)")
            continue

        funding_rate = _to_float(entry.get("funding_rate"))
        oi = entry.get("open_interest") or {}
        oi_long = _to_float(oi.get("long_open_interest"))
        oi_short = _to_float(oi.get("short_open_interest"))

        result[coin] = {
            "mark": _to_float(entry.get("mark_price")),
            # funding_rate は年率の小数(モジュール冒頭の注記を参照)
            "funding_apr_pct": None if funding_rate is None else funding_rate * 100,
            "oi_long": oi_long,
            "oi_short": oi_short,
            "oi_skew_pct": _oi_skew_pct(oi_long, oi_short),
            "volume_24h": _to_float(entry.get("volume_24h")),
            "spread_bps": _to_float(entry.get("base_spread_bps")),
        }

    return result


def _oi_skew_pct(oi_long: float | None, oi_short: float | None) -> float | None:
    """建玉の偏り% = (long - short) / (long + short) * 100。正ならロング過多。"""
    if oi_long is None or oi_short is None:
        return None
    total = oi_long + oi_short
    if total == 0:
        return None
    return (oi_long - oi_short) / total * 100
