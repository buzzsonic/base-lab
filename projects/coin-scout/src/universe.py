"""監視対象リストの構築: Hyperliquid上場銘柄 ∩ CEX(Binance/Bybit)出来高フィルタ。"""

from typing import Any

from shared.hyperliquid import HyperliquidClient

from .cex_volume import fetch_cex_volumes, max_cex_volume, normalize_hl_coin
from .config import Settings


def _to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_hl_assets(client: HyperliquidClient) -> list[dict[str, Any]]:
    """Hyperliquid perp全銘柄のスナップショットを返す(上場廃止銘柄は除外)。"""
    meta, asset_ctxs = client.meta_and_asset_ctxs()
    universe = meta.get("universe")
    if not isinstance(universe, list):
        raise ValueError("metaAndAssetCtxs の universe 応答形式が不正です。")

    assets: list[dict[str, Any]] = []
    for index, asset in enumerate(universe):
        if not isinstance(asset, dict) or asset.get("isDelisted"):
            continue
        coin = str(asset.get("name") or "")
        if not coin:
            continue
        ctx = asset_ctxs[index] if index < len(asset_ctxs) else {}
        mark_px = _to_float(ctx.get("markPx")) or _to_float(ctx.get("midPx"))
        oi_coin = _to_float(ctx.get("openInterest"))
        assets.append(
            {
                "coin": coin,
                "base": normalize_hl_coin(coin),
                "mark_px": mark_px,
                "prev_day_px": _to_float(ctx.get("prevDayPx")),
                "day_ntl_vlm": _to_float(ctx.get("dayNtlVlm")),
                "funding_hourly": _to_float(ctx.get("funding")),
                "funding_raw": _to_float(ctx.get("funding")),
                "funding_interval_hours": 1.0,
                "open_interest_coin": abs(oi_coin) if oi_coin is not None else None,
                "open_interest_usd": (
                    abs(oi_coin * mark_px) if oi_coin is not None and mark_px is not None else None
                ),
                "max_leverage": asset.get("maxLeverage"),
            }
        )
    return assets


def build_watchlist(
    client: HyperliquidClient,
    settings: Settings,
    logger: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """(監視対象リスト, HL全銘柄名リスト) を返す。

    全銘柄名リストは新規上場検知の差分比較用(フィルタ前のHL universe)。

    通過条件: Binance/Bybit直接の出来高 >= min_cex_volume_usd、または
    CoinGecko集計出来高 >= min_cex_volume_usd × multiplier。
    集計値は全取引所合算で直接値より甘くなるため倍率で補正する
    (GitHub ActionsランナーではBybit/Binance先物が地域ブロックされ、
    CoinGeckoが実質的なBybit代替になる)。
    """
    assets = fetch_hl_assets(client)
    logger.info(f"Hyperliquid上場銘柄: {len(assets)}銘柄")

    cex_volumes = fetch_cex_volumes(logger)
    if not cex_volumes:
        raise RuntimeError("CEX出来高の取得にすべて失敗しました。監視対象を決められません。")

    direct_min = settings.min_cex_volume_usd
    coingecko_min = settings.min_cex_volume_usd * settings.coingecko_volume_multiplier

    watchlist: list[dict[str, Any]] = []
    for asset in assets:
        entry = cex_volumes.get(asset["base"]) or {}
        direct = max((v for k, v in entry.items() if k != "coingecko"), default=0.0)
        coingecko = entry.get("coingecko", 0.0)
        if direct < direct_min and coingecko < coingecko_min:
            continue
        asset["cex_volume_usd"] = max_cex_volume(entry)
        asset["cex_sources"] = sorted(entry.keys())
        watchlist.append(asset)

    watchlist.sort(key=lambda a: a["cex_volume_usd"], reverse=True)
    logger.info(
        f"監視対象: {len(watchlist)}銘柄 (直接>=${direct_min:,.0f} または CoinGecko>=${coingecko_min:,.0f})"
    )
    return watchlist, [a["coin"] for a in assets]
