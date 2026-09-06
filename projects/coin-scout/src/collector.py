"""5分観測収集。方向予測をせず、全監視銘柄の検証可能な事実を保存する。"""

from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from shared.discord import send_discord_message
from shared.hyperliquid import HyperliquidApiError, HyperliquidClient
from shared.logging_utils import get_logger

from .config import load_settings
from .metrics import anomaly_score, high_low_from_snapshots, nearest_prior, pct_change, robust_funding_anomaly, trade_imbalance
from .notify import format_state_change_digest
from .observation_store import append_unique_gzip, build_outcomes, event_id, load_collector_state, observation_path, outcome_path, prune_history, save_collector_state
from .universe import build_watchlist, fetch_hl_assets


def _refresh_watchlist(client, settings, logger, state, now_ms):
    age=now_ms-int(state.get("watchlist_refreshed_at_ms",0))
    if age>=12*60*60*1000 or not state.get("watchlist_coins"):
        watchlist, all_coins=build_watchlist(client,settings,logger)
        state["watchlist_coins"]=[row["coin"] for row in watchlist]
        state["all_coins"]=all_coins; state["watchlist_refreshed_at_ms"]=now_ms
        return watchlist
    allowed=set(state["watchlist_coins"])
    return [row for row in fetch_hl_assets(client) if row["coin"] in allowed]


def _facts(features):
    facts=[]; p=features.get("price_change_15m_pct"); oi=features.get("oi_qty_change_15m_pct")
    if p is not None and oi is not None:
        if p>0 and oi>0: facts.append("価格上昇＋数量OI増加")
        elif p<0 and oi>0: facts.append("価格下落＋数量OI増加")
        elif abs(p)>=2 and oi<0: facts.append("建玉減少を伴う価格急変")
    flow=features.get("trade_imbalance_5m") or {}
    if flow.get("coverage_complete") and flow.get("normalized_imbalance") is not None:
        if flow["normalized_imbalance"]>=.35:facts.append("買い手主導約定の偏り")
        elif flow["normalized_imbalance"]<=-.35:facts.append("売り手主導約定の偏り")
    z=features.get("funding_robust_z")
    if z is not None and abs(z)>=3:facts.append("Fundingが銘柄自身の過去分布から乖離")
    pos=features.get("high_low") or {};normal=pos.get("observed_mean_abs_change_pct")
    if pos.get("path_samples",0)>=4 and normal:
        if pos.get("high_age_minutes",0)>=15 and abs(pos.get("from_high_pct",0))>=normal:facts.append(f"直近1時間高値を{pos['high_age_minutes']:.0f}分未更新（高値から{pos['from_high_pct']:+.2f}%）")
        if pos.get("low_age_minutes",0)>=15 and abs(pos.get("from_low_pct",0))>=normal:facts.append(f"直近1時間安値を{pos['low_age_minutes']:.0f}分未更新（安値から{pos['from_low_pct']:+.2f}%）")
    if not facts:facts.append("組合せ観測条件に大きな変化なし")
    return facts


def _features(asset, history, trades, funding_history, now_ms, settings, trade_status):
    features={"price_change_24h_pct":pct_change(asset["mark_px"],asset["prev_day_px"])}; timing={}; missing=[]
    for label,minutes in (("5m",5),("15m",15),("1h",60)):
        prior,error=nearest_prior(history,now_ms,minutes,settings.comparison_tolerance_minutes); timing[label]=error
        features[f"price_change_{label}_pct"]=pct_change(asset["mark_px"],prior.get("price") if prior else None)
        features[f"oi_qty_change_{label}_pct"]=pct_change(asset["open_interest_coin"],prior.get("open_interest_coin") if prior else None)
        if prior is None:missing.append(f"{label}比較点")
    funding=robust_funding_anomaly(asset["funding_hourly"],funding_history)
    features.update({"funding_raw":asset["funding_raw"],"funding_interval_hours":asset["funding_interval_hours"],"funding_hourly":asset["funding_hourly"],"funding_reference_days":settings.funding_reference_days,"funding_reference_samples":funding["reference_samples"],"funding_median_hourly":funding["median"],"funding_mad_hourly":funding["mad"],"funding_robust_z":funding["robust_z"]})
    features["trade_imbalance_5m"]=trade_imbalance(trades,now_ms-5*60_000,now_ms)
    features["trade_imbalance_15m"]=trade_imbalance(trades,now_ms-15*60_000,now_ms)
    features["trade_collection_status"]=trade_status
    features["high_low"]=high_low_from_snapshots(history,asset["mark_px"],now_ms)
    features["comparison_timing_error_minutes"]=timing
    if funding["reference_samples"]<24:missing.append("Funding過去分布")
    if not features["trade_imbalance_5m"]["coverage_complete"]:missing.append("5分約定全区間" if trade_status=="sampled" else "約定方向ローテーション対象外")
    core_keys=("price_change_5m_pct","price_change_15m_pct","price_change_1h_pct","price_change_24h_pct","oi_qty_change_5m_pct","oi_qty_change_15m_pct","oi_qty_change_1h_pct","funding_hourly")
    core_present=sum(features.get(key) is not None for key in core_keys)
    optional_present=sum((features["funding_robust_z"] is not None,features["trade_imbalance_5m"]["coverage_complete"],features["high_low"].get("from_high_pct") is not None))
    features["core_data_completeness_pct"]=round(core_present/len(core_keys)*100,1)
    features["data_completeness_pct"]=round((core_present+optional_present)/(len(core_keys)+3)*100,1); score,components=anomaly_score(features)
    features["anomaly_score"]=score;features["anomaly_components"]=components
    return features,missing


def run() -> int:
    logger=get_logger("coin-scout-collector");settings=load_settings();state=load_collector_state();now_ms=int(time.time()*1000)
    client=HyperliquidClient(request_sleep_seconds=.03,logger=logger); observations=[]
    try:
        watchlist=_refresh_watchlist(client,settings,logger,state,now_ms);now_ms=int(time.time()*1000)
        if settings.collector_max_coins>0:watchlist=watchlist[:settings.collector_max_coins]
        history=state.setdefault("history",{});funding_state=state.setdefault("funding_hourly",{})
        previous_run=state.get("last_run_ms");run_gap_minutes=(now_ms-previous_run)/60_000 if previous_run else None
        sample_count=min(max(settings.trade_sample_coins_per_run,0),len(watchlist))
        sample_start=(now_ms//300_000*max(sample_count,1))%max(len(watchlist),1)
        sampled={watchlist[(sample_start+offset)%len(watchlist)]["coin"] for offset in range(sample_count)} if watchlist else set()
        for index,asset in enumerate(watchlist):
            coin=asset["coin"]; errors=[];trades=[]
            trade_status="not_sampled_rate_limit_control"
            if coin in sampled:
                try:trades=client.recent_trades(coin);trade_status="sampled"
                except HyperliquidApiError as exc:errors.append(f"trades:{exc}");trade_status="api_error"
            prior_rows=history.get(coin,[]); hourly=funding_state.setdefault(coin,[])
            historical_values=[row["value"] for row in hourly if row["hour_ms"] < (now_ms//3_600_000)*3_600_000]
            features,missing=_features(asset,prior_rows,trades,historical_values,now_ms,settings,trade_status)
            if run_gap_minutes is not None and run_gap_minutes>settings.observation_interval_minutes+settings.comparison_tolerance_minutes:missing.append(f"前回から{run_gap_minutes:.1f}分の収集間隔")
            source_time=None;freshness=None;missing.append("metaAndAssetCtxsはデータ元時刻を提供しない")
            eid=event_id("hyperliquid",coin,now_ms,settings.logic_version);facts=_facts(features)
            fired=features["anomaly_score"] is not None and features["anomaly_score"]>=settings.state_alert_min_anomaly and features["data_completeness_pct"]>=60
            decision="fired" if fired else ("insufficient" if features["core_data_completeness_pct"]<75 else "not_fired")
            reasons=facts if fired else ((["中核時系列の充足度不足"]+missing) if decision=="insufficient" else ["異常度閾値未満"]+missing)
            row={"event_id":eid,"observed_at_ms":now_ms,"observed_at_utc":datetime.fromtimestamp(now_ms/1000,timezone.utc).isoformat(),"source_at_ms":source_time,"source_timestamp_status":"not_provided_by_metaAndAssetCtxs","symbol":coin,"exchange":"hyperliquid","price":asset["mark_px"],"open_interest_coin":asset["open_interest_coin"],"open_interest_usd":asset["open_interest_usd"],"funding_raw":asset["funding_raw"],"funding_interval_hours":1.0,"funding_hourly":asset["funding_hourly"],"volume_24h_usd":asset["day_ntl_vlm"],"features":features,"observed_facts":facts,"decision":decision,"decision_reasons":reasons,"missing_fields":missing,"freshness_seconds":freshness,"interval_coverage":{"scheduled_minutes":settings.observation_interval_minutes,"actual_gap_minutes":run_gap_minutes,"interpolated":False},"logic_version":settings.logic_version,"config":{"comparison_tolerance_minutes":settings.comparison_tolerance_minutes,"funding_reference_days":settings.funding_reference_days,"state_alert_min_anomaly":settings.state_alert_min_anomaly,"state_alert_cooldown_minutes":settings.state_alert_cooldown_minutes,"trade_sample_coins_per_run":settings.trade_sample_coins_per_run,"anomaly_weights":{"price":30,"oi_quantity":25,"funding":15,"taker_flow":20}},"errors":errors}
            observations.append(row)
            compact={"event_id":eid,"observed_at_ms":now_ms,"price":asset["mark_px"],"open_interest_coin":asset["open_interest_coin"],"decision":decision}
            if not any(existing.get("event_id")==eid for existing in history.setdefault(coin,[])):history[coin].append(compact)
            hour=(now_ms//3_600_000)*3_600_000
            if asset["funding_hourly"] is not None and not any(x["hour_ms"]==hour for x in hourly):hourly.append({"hour_ms":hour,"value":asset["funding_hourly"]})
            cutoff=now_ms-settings.funding_reference_days*86_400_000;funding_state[coin]=[x for x in hourly if x["hour_ms"]>=cutoff]
            if index and index%25==0:logger.info(f"収集 {index}/{len(watchlist)}")
        prune_history(history,now_ms); added=append_unique_gzip(observation_path(now_ms),observations,"event_id")
        outcomes=build_outcomes(history,now_ms,settings.comparison_tolerance_minutes)
        outcomes=[row for row in outcomes if previous_run is not None and previous_run < row["target_at_ms"] <= now_ms]
        outcome_added=append_unique_gzip(outcome_path(now_ms),outcomes,"outcome_id") if outcomes else 0
        state["last_run_ms"]=now_ms;save_collector_state(state);logger.info(f"観測保存: {added}/{len(observations)}、将来結果: {outcome_added}")
        if settings.state_alerts_enabled:
            message,alert_updates=format_state_change_digest(observations,state.get("alerts",{}),now_ms,settings)
            if message:
                send_discord_message(webhook_url=settings.discord_webhook_url,message=message,dry_run=settings.dry_run,logger=logger)
                state.setdefault("alerts",{}).update(alert_updates);save_collector_state(state)
        return 0
    except Exception as exc:
        logger.error(f"収集失敗: {exc}");traceback.print_exc();return 1


def main():sys.exit(run())
if __name__=="__main__":main()
