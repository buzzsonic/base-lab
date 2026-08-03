"""乖離指標の計算: 実効ドル円 / 国内取引所間クロス / HL現物-パープのベーシス / FR年率換算 /
ポイ活DEX(Variational・Nado)とHLのFR差・価格差。"""

from itertools import permutations
from typing import Any

from .config import HL_SPOT_BASIS_TARGETS

HOURS_PER_YEAR = 24 * 365


def domestic_mid(domestic: dict[str, dict[str, dict[str, float]]], coin: str) -> float | None:
    """複数取引所のbid/askからその銘柄の代表mid(単純平均)を返す。1つも取得できていなければNone。"""
    mids: list[float] = []
    for exchange_data in domestic.values():
        entry = exchange_data.get(coin)
        if entry is None:
            continue
        mids.append((entry["bid"] + entry["ask"]) / 2)
    if not mids:
        return None
    return sum(mids) / len(mids)


def compute_effective_usdjpy(
    domestic_mid_value: float | None, hl_perp_mid: float | None, usdjpy_ref: float | None
) -> tuple[float | None, float | None]:
    """実効ドル円と、参照USDJPYからの乖離%を返す。"""
    if domestic_mid_value is None or hl_perp_mid in (None, 0):
        return None, None
    effective = domestic_mid_value / hl_perp_mid
    dev_pct = None
    if usdjpy_ref not in (None, 0):
        dev_pct = (effective / usdjpy_ref - 1) * 100
    return effective, dev_pct


def compute_domestic_cross(
    domestic: dict[str, dict[str, dict[str, float]]], coin: str
) -> tuple[float | None, str | None]:
    """同一銘柄で「ある所のbest bidが別の所のbest askを上回る」クロス幅%のうち最良の組み合わせを返す。

    全ての取引所ペア(順序あり、自分同士は除く)について (bid_i - ask_j) / ask_j * 100 を計算し、
    最大値を採用する。正の値であれば実際にクロスしている(裁定余地あり)。負でも「最も近い組み合わせ」
    として記録する(アラート閾値との比較に使うため)。
    """
    quotes = {
        exchange: entry[coin]
        for exchange, entry in domestic.items()
        if coin in entry
    }
    if len(quotes) < 2:
        return None, None

    best_pct: float | None = None
    best_pair: str | None = None
    for bid_exchange, ask_exchange in permutations(quotes.keys(), 2):
        bid = quotes[bid_exchange]["bid"]
        ask = quotes[ask_exchange]["ask"]
        if ask == 0:
            continue
        cross_pct = (bid - ask) / ask * 100
        if best_pct is None or cross_pct > best_pct:
            best_pct = cross_pct
            best_pair = f"{bid_exchange}(bid)>{ask_exchange}(ask)"
    return best_pct, best_pair


def compute_funding_apr(funding_hourly: float | None) -> float | None:
    if funding_hourly is None:
        return None
    return funding_hourly * HOURS_PER_YEAR * 100


def compute_hl_basis(spot_mid: float | None, perp_mid: float | None) -> float | None:
    """HL現物-パープのベーシス% = (spot - perp) / perp * 100。"""
    if spot_mid is None or perp_mid in (None, 0):
        return None
    return (spot_mid - perp_mid) / perp_mid * 100


def compute_price_dev_pct(venue_price: float | None, hl_perp_mid: float | None) -> float | None:
    """ポイ活DEXの価格がHLパープからどれだけ乖離しているか% = (venue - hl) / hl * 100。"""
    if venue_price is None or hl_perp_mid in (None, 0):
        return None
    return (venue_price - hl_perp_mid) / hl_perp_mid * 100


def compute_fr_spread(venue_apr_pct: float | None, hl_apr_pct: float | None) -> float | None:
    """FR年率の差(ベニュー - HL)。正ならベニュー側のロングがHLより高い金利を払っている。

    ポイ活勢は「ボリュームを作る」のが目的で価格・金利に無頓着なため、この差が恒常的に
    開くかどうかが検証したい仮説そのもの。判断はせず差の記録だけ行う。
    """
    if venue_apr_pct is None or hl_apr_pct is None:
        return None
    return venue_apr_pct - hl_apr_pct


def build_pointfarm_metrics(
    pointfarm_coins: tuple[str, ...],
    hl_perp: dict[str, dict[str, float | None]],
    variational: dict[str, dict[str, float | None]],
    nado: dict[str, dict[str, float | None]],
) -> dict[str, Any]:
    """ポイ活DEX2社×HLの比較指標をコイン名→{...}で返す。"""
    result: dict[str, Any] = {}
    for coin in pointfarm_coins:
        hl_ctx = hl_perp.get(coin, {})
        hl_mid = hl_ctx.get("mid")
        hl_apr = compute_funding_apr(hl_ctx.get("funding_hourly"))

        var = variational.get(coin, {})
        nad = nado.get(coin, {})
        var_apr = var.get("funding_apr_pct")
        nado_apr = nad.get("funding_apr_pct")

        result[coin] = {
            "hl_perp_mid": hl_mid,
            "hl_funding_apr_pct": hl_apr,
            "var_mark": var.get("mark"),
            "var_funding_apr_pct": var_apr,
            "var_oi_skew_pct": var.get("oi_skew_pct"),
            "var_volume_24h": var.get("volume_24h"),
            "var_spread_bps": var.get("spread_bps"),
            "var_hl_dev_pct": compute_price_dev_pct(var.get("mark"), hl_mid),
            "var_hl_fr_spread_apr_pct": compute_fr_spread(var_apr, hl_apr),
            "nado_mid": nad.get("mid"),
            "nado_oracle": nad.get("oracle"),
            "nado_open_interest": nad.get("open_interest"),
            "nado_funding_apr_pct": nado_apr,
            "nado_hl_dev_pct": compute_price_dev_pct(nad.get("mid"), hl_mid),
            "nado_hl_fr_spread_apr_pct": compute_fr_spread(nado_apr, hl_apr),
        }
    return result


def build_metrics(
    coins: tuple[str, ...],
    domestic: dict[str, dict[str, dict[str, float]]],
    hl_perp: dict[str, dict[str, float | None]],
    hl_spot_mids: dict[str, float],
    usdjpy_ref: float | None,
    pointfarm_coins: tuple[str, ...] = (),
    variational: dict[str, dict[str, float | None]] | None = None,
    nado: dict[str, dict[str, float | None]] | None = None,
) -> dict[str, Any]:
    per_coin: dict[str, Any] = {}
    for coin in coins:
        d_mid = domestic_mid(domestic, coin)
        perp_ctx = hl_perp.get(coin, {})
        perp_mid = perp_ctx.get("mid")
        funding_hourly = perp_ctx.get("funding_hourly")

        effective_usdjpy, dev_pct = compute_effective_usdjpy(d_mid, perp_mid, usdjpy_ref)
        cross_pct, cross_pair = compute_domestic_cross(domestic, coin)
        funding_apr_pct = compute_funding_apr(funding_hourly)

        per_coin[coin] = {
            "domestic_mid": d_mid,
            "hl_perp_mid": perp_mid,
            "hl_perp_funding_hourly": funding_hourly,
            "funding_apr_pct": funding_apr_pct,
            "effective_usdjpy": effective_usdjpy,
            "effective_usdjpy_dev_pct": dev_pct,
            "domestic_cross_pct": cross_pct,
            "domestic_cross_pair": cross_pair,
        }

    hl_basis: dict[str, Any] = {}
    for spot_token, perp_coin in HL_SPOT_BASIS_TARGETS.items():
        spot_mid = hl_spot_mids.get(spot_token)
        perp_mid = hl_perp.get(perp_coin, {}).get("mid")
        hl_basis[spot_token] = {
            "spot_mid": spot_mid,
            "perp_mid": perp_mid,
            "basis_pct": compute_hl_basis(spot_mid, perp_mid),
        }

    pointfarm = build_pointfarm_metrics(
        pointfarm_coins, hl_perp, variational or {}, nado or {}
    )

    return {"per_coin": per_coin, "hl_basis": hl_basis, "pointfarm": pointfarm}
