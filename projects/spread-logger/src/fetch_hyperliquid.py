"""Hyperliquid info APIからパープのmid/funding、現物(HYPE/UBTC/UETH/USOL)のmidを取得する。

現物ミッドは metaAndAssetCtxs 系のspot版(spotMetaAndAssetCtxs)のasset_ctxsを使わない。
実機検証したところ、そのasset_ctxs配列はuniverseのリスト順と対応しておらず(全く違う値になる)、
一方で allMids の "@{pair_index}" キーはperpの同一銘柄のmid/実勢と整合していた。そのため
spot_meta()(pair_index → "BASE/QUOTE" 名の対応表)と all_mids()(価格そのもの)を組み合わせて使う。
"""

from typing import Any

from shared.hyperliquid import HyperliquidClient

from .config import HL_SPOT_BASIS_TARGETS


def fetch_perp_contexts(
    client: HyperliquidClient, coins: tuple[str, ...], logger: Any
) -> dict[str, dict[str, float | None]]:
    """パープのmid/fundingをコイン名→{"mid":.., "funding_hourly":..}で返す。

    coinsに加えてHL現物ベーシス計算に必要なperp銘柄(HYPE等)もまとめて渡すこと。
    """
    try:
        contexts = client.market_contexts(coins)
    except Exception as exc:  # noqa: BLE001 - HL障害時も他の取得を続けたい
        logger.error(f"Hyperliquid: パープ情報の取得に失敗: {exc}")
        return {}

    result: dict[str, dict[str, float | None]] = {}
    for coin in coins:
        ctx = contexts.get(coin.upper())
        if ctx is None:
            logger.warning(f"Hyperliquid: パープ {coin} が見つかりません")
            continue
        result[coin] = {"mid": ctx.get("mid_px") or ctx.get("mark_px"), "funding_hourly": ctx.get("funding")}
    return result


def fetch_spot_mids(client: HyperliquidClient, logger: Any) -> dict[str, float]:
    """HL現物(HYPE/UBTC/UETH/USOL)のUSDC建てmidをトークン名→midで返す。"""
    try:
        pairs = client.spot_meta()  # "@N" -> "BASE/QUOTE"
        mids = client.all_mids()  # "@N" -> price (perpは銘柄名そのもの)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Hyperliquid: 現物情報の取得に失敗: {exc}")
        return {}

    targets = set(HL_SPOT_BASIS_TARGETS.keys())
    result: dict[str, float] = {}
    for key, name in pairs.items():
        if "/" not in name:
            continue
        base, quote = name.split("/", 1)
        if base not in targets or quote != "USDC":
            continue
        mid = mids.get(key)
        if mid is None:
            continue
        # 同一トークンに複数USDCペアが存在することはない想定だが、念のため最初に見つかったものを採用
        result.setdefault(base, mid)

    missing = targets - result.keys()
    if missing:
        logger.warning(f"Hyperliquid: 現物mid取得できず: {sorted(missing)}")
    return result
