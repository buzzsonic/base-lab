"""監視対象リストの構築: Hyperliquid上場銘柄 ∩ CEX(Binance/Bybit)出来高フィルタ。"""

from typing import Any

from shared.hyperliquid import HyperliquidClient

from .cex_volume import fetch_cex_volumes, max_cex_volume, normalize_hl_coin


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
                "open_interest_usd": (
                    abs(oi_coin * mark_px) if oi_coin is not None and mark_px is not None else None
                ),
                "max_leverage": asset.get("maxLeverage"),
            }
        )
    return assets


def build_watchlist(
    client: HyperliquidClient,
    min_cex_volume_usd: float,
    logger: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """(監視対象リスト, HL全銘柄名リスト) を返す。

    全銘柄名リストは新規上場検知の差分比較用(フィルタ前のHL universe)。
    """
    assets = fetch_hl_assets(client)
    logger.info(f"Hyperliquid上場銘柄: {len(assets)}銘柄")

    cex_volumes = fetch_cex_volumes(logger)
    if not cex_volumes:
        raise RuntimeError("Binance/Bybit両方の出来高取得に失敗しました。監視対象を決められません。")

    watchlist: list[dict[str, Any]] = []
    for asset in assets:
        entry = cex_volumes.get(asset["base"])
        volume = max_cex_volume(entry)
        if volume < min_cex_volume_usd:
            continue
        asset["cex_volume_usd"] = volume
        asset["cex_sources"] = sorted(entry.keys()) if entry else []
        watchlist.append(asset)

    watchlist.sort(key=lambda a: a["cex_volume_usd"], reverse=True)
    logger.info(
        f"監視対象: {len(watchlist)}銘柄 (CEX24h出来高 >= ${min_cex_volume_usd:,.0f})"
    )
    return watchlist, [a["coin"] for a in assets]
