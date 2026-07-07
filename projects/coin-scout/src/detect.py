"""検知ロジック3本柱: 出来高・価格の急変動 / ファンディング・OIの偏り / 新規上場。"""

import time
from datetime import datetime, timedelta
from typing import Any

from shared.hyperliquid import HyperliquidApiError, HyperliquidClient

from .config import Settings

# OIがこの額(USD)未満の銘柄はOI変化率のノイズが大きいため判定しない
MIN_OI_USD_FOR_CHANGE = 5_000_000
# 出来高ベースラインに最低限必要な過去日数
MIN_BASELINE_DAYS = 3
HOURS_PER_YEAR = 24 * 365


def fetch_volume_baselines(
    client: HyperliquidClient,
    coins: list[str],
    baseline_days: int,
    logger: Any,
) -> dict[str, float]:
    """銘柄ごとの日次出来高(USD)ベースライン(直近N日平均、当日は除く)を返す。"""
    end = datetime.now()
    start = end - timedelta(days=baseline_days + 2)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    baselines: dict[str, float] = {}
    failed = 0
    for coin in coins:
        try:
            candles = client.candle_snapshot(coin, "1d", start_ms, end_ms)
        except HyperliquidApiError as exc:
            failed += 1
            logger.warning(f"ローソク足取得失敗: {coin} / {exc}")
            continue
        finally:
            time.sleep(0.2)

        daily_notionals: list[tuple[int, float]] = []
        for candle in candles:
            try:
                open_ms = int(candle["t"])
                notional = float(candle["v"]) * float(candle["c"])
            except (KeyError, TypeError, ValueError):
                continue
            daily_notionals.append((open_ms, notional))

        daily_notionals.sort()
        # 最後の足は進行中の当日分なので除外し、直近baseline_days日で平均する
        full_days = daily_notionals[:-1][-baseline_days:]
        if len(full_days) < MIN_BASELINE_DAYS:
            continue
        average = sum(notional for _, notional in full_days) / len(full_days)
        if average > 0:
            baselines[coin] = average

    logger.info(f"出来高ベースライン計算: {len(baselines)}/{len(coins)}銘柄 (取得失敗{failed}件)")
    return baselines


def build_report(
    watchlist: list[dict[str, Any]],
    all_coins: list[str],
    baselines: dict[str, float],
    previous_state: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    previous_coins = set(previous_state["coins"]) if previous_state else None
    previous_oi = previous_state["oi_usd"] if previous_state else {}

    alerts: list[dict[str, Any]] = []
    for asset in watchlist:
        signals = _evaluate_asset(asset, baselines, previous_oi, settings)
        if signals["reasons"]:
            alerts.append(signals)

    # スコア(発火シグナル数)→ 変動の大きさで並べる
    alerts.sort(key=lambda a: (a["score"], abs(a["chg_pct"] or 0.0)), reverse=True)

    new_listings: list[str] = []
    if previous_coins is not None:
        new_listings = sorted(set(all_coins) - previous_coins)

    return {
        "alerts": alerts[: settings.max_alerts],
        "total_fired": len(alerts),
        "new_listings": new_listings,
        "watchlist_size": len(watchlist),
    }


def _evaluate_asset(
    asset: dict[str, Any],
    baselines: dict[str, float],
    previous_oi: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    coin = asset["coin"]
    reasons: list[str] = []

    chg_pct: float | None = None
    if asset["mark_px"] and asset["prev_day_px"]:
        chg_pct = (asset["mark_px"] / asset["prev_day_px"] - 1) * 100

    # 1) 出来高急増 + 価格変動
    vol_ratio: float | None = None
    baseline = baselines.get(coin)
    if baseline and asset["day_ntl_vlm"]:
        vol_ratio = asset["day_ntl_vlm"] / baseline
        if (
            vol_ratio >= settings.volume_spike_ratio
            and chg_pct is not None
            and abs(chg_pct) >= settings.price_move_min_pct
        ):
            reasons.append(f"出来高急増 {vol_ratio:.1f}倍(7日平均比) + 価格{chg_pct:+.1f}%")

    # 2a) ファンディングの偏り
    # 逆張り示唆はしない: 2026-07のバックテストで極端FRは反転でなく継続シグナルと確定済み
    funding_apr: float | None = None
    funding_fired = False
    if asset["funding_hourly"] is not None:
        funding_apr = asset["funding_hourly"] * HOURS_PER_YEAR * 100
        if abs(funding_apr) >= settings.funding_apr_alert_pct:
            funding_fired = True
            side = "ロング混雑" if funding_apr > 0 else "ショート混雑"
            reasons.append(f"ファンディング偏り 年率{funding_apr:+.0f}% → {side}")

    # 2b) OI急増(前回スキャン比)
    oi_change_pct: float | None = None
    oi_now = asset["open_interest_usd"]
    oi_prev = previous_oi.get(coin)
    if oi_now and isinstance(oi_prev, (int, float)) and oi_prev > 0 and oi_now >= MIN_OI_USD_FOR_CHANGE:
        oi_change_pct = (oi_now / oi_prev - 1) * 100
        if oi_change_pct >= settings.oi_change_alert_pct:
            reasons.append(f"OI急増 {oi_change_pct:+.0f}%(前回比) → 新規資金の流入")

    return {
        "coin": coin,
        "mark_px": asset["mark_px"],
        "chg_pct": chg_pct,
        "vol_ratio": vol_ratio,
        "funding_apr": funding_apr,
        "oi_change_pct": oi_change_pct,
        "oi_usd": oi_now,
        "cex_volume_usd": asset.get("cex_volume_usd"),
        "hl_volume_usd": asset["day_ntl_vlm"],
        "funding_fired": funding_fired,
        "reasons": reasons,
        "score": len(reasons),
    }
