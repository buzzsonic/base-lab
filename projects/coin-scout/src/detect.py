"""朝夜ダイジェスト用の観測ロジック。方向優位性は判定しない。"""

import time
import math
from datetime import datetime, timedelta, timezone
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
        today_utc_ms = (end_ms // 86_400_000) * 86_400_000
        for candle in candles:
            try:
                open_ms = int(candle["t"])
                notional = float(candle["v"]) * float(candle["c"])
            except (KeyError, TypeError, ValueError):
                continue
            if open_ms < today_utc_ms and math.isfinite(notional) and notional > 0:
                daily_notionals.append((open_ms, notional))

        daily_notionals.sort()
        # UTC当日の未確定足を時刻で除外（APIが確定足のみ返しても末尾を落とさない）
        full_days = daily_notionals[-baseline_days:]
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
    now_ms: int | None = None,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    previous_state = previous_state or {}
    previous_coins = set(previous_state["coins"]) if "coins" in previous_state else None
    previous_at = previous_state.get("observed_at_ms")
    if previous_at is None and previous_state.get("generated_at_jst"):
        try:
            stamp = datetime.strptime(previous_state["generated_at_jst"], "%Y-%m-%d %H:%M:%S JST")
            previous_at = stamp.replace(tzinfo=timezone(timedelta(hours=9))).timestamp() * 1000
        except (TypeError, ValueError):
            pass
    gap_hours = (now_ms - previous_at) / 3_600_000 if isinstance(previous_at, (int, float)) else None
    comparable = gap_hours is not None and 1 <= gap_hours <= settings.digest_max_comparison_hours
    # 旧ドル建てstateから数量は推測しない。移行初回は比較不足を表示する。
    previous_oi = previous_state.get("oi_coin", {}) if comparable else {}
    alerts = []
    funding_only = 0
    excluded = 0
    missing_oi = 0
    missing_baselines = 0
    for asset in watchlist:
        if (asset.get("day_ntl_vlm") or 0) < settings.min_hl_volume_usd:
            excluded += 1
            continue
        row = _evaluate_asset(asset, baselines, previous_oi, settings)
        missing_oi += row["oi_change_pct"] is None
        missing_baselines += row["vol_ratio"] is None
        if row["reasons"]:
            alerts.append(row)
        elif row["funding_fired"]:
            funding_only += 1
    alerts.sort(key=lambda a: (a["score"], abs(a["oi_change_pct"] or 0), abs(a["chg_pct"] or 0)), reverse=True)
    return {
        "alerts": alerts[:settings.max_alerts], "total_fired": len(alerts),
        "new_listings": sorted(set(all_coins) - previous_coins) if previous_coins is not None else [],
        "watchlist_size": len(watchlist), "eligible_size": len(watchlist) - excluded,
        "liquidity_excluded": excluded, "funding_only_count": funding_only,
        "missing_oi_count": missing_oi, "missing_baseline_count": missing_baselines,
        "comparison_hours": gap_hours if comparable else None,
        "baseline_days": settings.baseline_days,
    }


def _evaluate_asset(asset, baselines, previous_oi, settings):
    coin = asset["coin"]
    reasons = []
    chg_pct = (asset["mark_px"] / asset["prev_day_px"] - 1) * 100 if asset["mark_px"] and asset["prev_day_px"] else None
    baseline = baselines.get(coin)
    vol_ratio = asset["day_ntl_vlm"] / baseline if baseline and asset["day_ntl_vlm"] is not None else None
    volume_fired = vol_ratio is not None and vol_ratio >= settings.volume_spike_ratio and chg_pct is not None and abs(chg_pct) >= settings.price_move_min_pct
    if volume_fired:
        reasons.append(f"24h出来高 {vol_ratio:.1f}倍（過去最大{settings.baseline_days}確定日平均との概算比較）＋価格{chg_pct:+.1f}%/24h")
    funding = asset.get("funding_hourly")
    funding_apr = funding * HOURS_PER_YEAR * 100 if funding is not None else None
    funding_fired = funding_apr is not None and abs(funding_apr) >= settings.funding_apr_alert_pct
    oi_now = asset.get("open_interest_usd")
    qty = asset.get("open_interest_coin")
    prev = previous_oi.get(coin)
    oi_change = (qty / prev - 1) * 100 if qty is not None and isinstance(prev, (int, float)) and prev > 0 else None
    oi_fired = oi_change is not None and abs(oi_change) >= settings.oi_change_alert_pct and (oi_now or 0) >= MIN_OI_USD_FOR_CHANGE
    if oi_fired:
        reasons.append(f"数量OI {oi_change:+.1f}%（前回実測比）")
    # Funding単独では候補を作らず、選ばれた銘柄の補足情報として表示する。
    return {"coin": coin, "mark_px": asset["mark_px"], "chg_pct": chg_pct,
            "vol_ratio": vol_ratio, "funding_apr": funding_apr, "funding_hourly": funding,
            "oi_change_pct": oi_change, "oi_usd": oi_now,
            "cex_volume_usd": asset.get("cex_volume_usd"), "hl_volume_usd": asset["day_ntl_vlm"],
            "funding_fired": funding_fired, "reasons": reasons,
            "score": int(volume_fired) + int(oi_fired)}
