"""Discordダイジェストの整形。"""

from datetime import datetime
from typing import Any

# Discordのcontent上限2000文字に対する安全マージン
MESSAGE_LIMIT = 1900
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def format_price(price: float | None) -> str:
    if price is None:
        return "-"
    if price >= 1000:
        return f"${price:,.0f}"
    if price >= 1:
        return f"${price:,.2f}"
    return f"${price:.4g}"


def format_usd_millions(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e7:
        return f"${value / 1e6:.0f}M"
    return f"${value / 1e6:.1f}M"


def format_digest(report: dict[str, Any], run_at_jst: datetime) -> str:
    from .health import health_text
    lines = [f"🔎 **Coin Scout 観測ダイジェスト** {run_at_jst:%m/%d %H:%M} JST",
             f"候補{report['watchlist_size']} / HL流動性条件通過{report['eligible_size']} / 注目{report['total_fired']}銘柄",
             "注目順位＝観測条件。売買方向・勝率ではありません",
             health_text(report.get("collection_health"))]
    gap = report.get("comparison_hours")
    lines.append(f"数量OI比較: {gap:.1f}時間前の実測" if gap is not None else "数量OI比較: 有効な前回時刻なし")
    lines.append(f"比較不足: 数量OI {report['missing_oi_count']}銘柄 / 出来高基準 {report['missing_baseline_count']}銘柄")
    lines.append(f"Funding単独{report['funding_only_count']}銘柄は候補外 / HL薄商い{report['liquidity_excluded']}銘柄は除外")
    footer = "\n※ 出来高は24h値と日足終値×数量の概算平均の比較。Fundingは1時間率。注文の約定可能性・利益は未評価"
    shown = 0
    for alert in report["alerts"]:
        chg = _pct(alert["chg_pct"])
        funding = f"{alert['funding_hourly'] * 100:+.4f}%/時" if alert.get("funding_hourly") is not None else "不足"
        block = (f"\n**{alert['coin']}** {format_price(alert['mark_px'])} / {chg}/24h\n"
                 + "\n".join("・" + r for r in alert["reasons"])
                 + f"\nHL出来高 {format_usd_millions(alert['hl_volume_usd'])} / OI {format_usd_millions(alert['oi_usd'])} / Funding {funding}")
        if len("\n".join(lines) + block + footer) > MESSAGE_LIMIT - 160:
            break
        lines.append(block); shown += 1
    if not report["alerts"]:
        lines.append("取得できた条件では候補なし。比較不足の項目は未判定です")
    if report["total_fired"] > shown:
        lines.append(f"他{report['total_fired'] - shown}銘柄は表示枠外")
    if report["new_listings"]:
        names = ", ".join(report["new_listings"][:8])
        lines.append(f"新規観測銘柄: {names}（前回との差分。上場時刻は未確認）")
    return "\n".join(lines) + footer


def format_error_message(error: str, run_at_jst: datetime) -> str:
    return (
        f"🚨 **coin-scout 実行エラー** {run_at_jst.strftime('%m/%d %H:%M')} JST\n"
        f"```\n{error[:500]}\n```"
    )


def _pct(value: float | None) -> str:
    return "不足" if value is None else f"{value:+.2f}%"


def format_state_change_digest(
    observations: list[dict[str, Any]], previous_alerts: dict[str, Any], now_ms: int, settings
) -> tuple[str | None, dict[str, Any]]:
    """異常度上位の重要な状態変化だけを通知する。方向期待値は含めない。"""
    candidates=[];updates={}
    for row in observations:
        score=row["features"].get("anomaly_score")
        if row.get("decision")!="fired" or score is None:continue
        key=row["symbol"];facts=tuple(row.get("observed_facts",[]));band=int(score//10)
        previous=previous_alerts.get(key,{})
        cooldown=bool(previous) and now_ms-int(previous.get("notified_at_ms",0)) < settings.state_alert_cooldown_minutes*60_000
        elapsed = now_ms - int(previous.get("notified_at_ms", 0))
        escalated = elapsed >= 15 * 60_000 and band >= int(previous.get("band", -99)) + 2
        if cooldown and not escalated:continue
        candidates.append(row)
    candidates.sort(key=lambda row:(row["features"].get("anomaly_score") or 0,row["features"].get("data_completeness_pct") or 0),reverse=True)
    candidates=candidates[:settings.state_alert_top_n]
    if not candidates:return None,updates
    lines=["🔬 **coin-scout 観測状態の重要変化**","異常度順（勝ちやすさ・方向予測ではありません）",""]
    for row in candidates:
        block_start = len(lines)
        f=row["features"];flow=f.get("trade_imbalance_5m") or {};pos=f.get("high_low") or {}
        lines.append(f"**{row['symbol']}** / {row['observed_at_utc']} / 異常度 {f['anomaly_score']:.1f} / 充足度 {f['data_completeness_pct']:.0f}%")
        lines.append("観測: "+"、".join(row["observed_facts"]))
        lines.append(f"価格 5m {_pct(f.get('price_change_5m_pct'))} / 15m {_pct(f.get('price_change_15m_pct'))} / 1h {_pct(f.get('price_change_1h_pct'))} / 24h {_pct(f.get('price_change_24h_pct'))}")
        lines.append(f"数量OI 5m {_pct(f.get('oi_qty_change_5m_pct'))} / 15m {_pct(f.get('oi_qty_change_15m_pct'))} / 1h {_pct(f.get('oi_qty_change_1h_pct'))}")
        funding_z=f.get("funding_robust_z"); funding_text="蓄積中" if funding_z is None else f"robust-z {funding_z:+.2f} (n={f.get('funding_reference_samples')})"
        flow_text="取得不足" if not flow.get("coverage_complete") else f"{(flow.get('normalized_imbalance') or 0):+.2f} (B=買い手主導/A=売り手主導)"
        lines.append(f"Funding {funding_text} / 5m約定偏り {flow_text}")
        lines.append(f"1h観測点高値から {_pct(pos.get('from_high_pct'))} / 観測点安値から {_pct(pos.get('from_low_pct'))}")
        missing="、".join(row.get("missing_fields",[])) or "なし";lines.append(f"鮮度 {row.get('freshness_seconds') if row.get('freshness_seconds') is not None else '不明'}秒 / 欠測: {missing}")
        lines.append("次の観察: 数量OIと約定偏りの継続、高値・安値更新、欠測解消を次回実測で確認")
        lines.append("")
        if len("\n".join(lines)) > MESSAGE_LIMIT:
            del lines[block_start:]
            break
        updates[row["symbol"]]={"notified_at_ms":now_ms,"facts":row["observed_facts"],"band":int(f["anomaly_score"]//10),"event_id":row["event_id"]}
    message="\n".join(lines)
    return (message if updates else None), updates
