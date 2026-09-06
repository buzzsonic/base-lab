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
    header = (
        f"🔎 **coin-scout 市場異常スキャン** "
        f"{run_at_jst.strftime('%m/%d')}({WEEKDAYS_JA[run_at_jst.weekday()]}) "
        f"{run_at_jst.strftime('%H:%M')} JST"
    )
    sub = f"監視{report['watchlist_size']}銘柄(HL上場 ∩ CEX出来高$10M+)中 {report['total_fired']}銘柄が発火"

    lines = [header, sub, ""]

    for alert in report["alerts"]:
        chg = f"{alert['chg_pct']:+.1f}%" if alert["chg_pct"] is not None else "-"
        conditions = f"観測条件{alert['score']}件"
        lines.append(f"**{alert['coin']}** {format_price(alert['mark_px'])} ({chg}/24h) / {conditions}")
        for reason in alert["reasons"]:
            lines.append(f"・{reason}")
        context = (
            f"　HL出来高 {format_usd_millions(alert['hl_volume_usd'])}"
            f" / OI {format_usd_millions(alert['oi_usd'])}"
            f" / CEX出来高 {format_usd_millions(alert['cex_volume_usd'])}"
        )
        lines.append(context)

    if not report["alerts"]:
        lines.append("本日の該当なし。閾値を超える動きはありませんでした。")

    if any(alert.get("funding_fired") for alert in report["alerts"]):
        lines.append("")
        lines.append("※ Funding年率は1時間率の単純換算。固定利回り・方向優位性・参加者の捕まりを示しません")

    if report["new_listings"]:
        lines.append("")
        listed = ", ".join(report["new_listings"])
        lines.append(f"🆕 HL新規上場: **{listed}**")
        lines.append("⚠️ 上場直後・イベント系は2025年の主要損失源(ALPACA/LUCE等)。触るならサイズ最小で")

    if report["total_fired"] > len(report["alerts"]):
        lines.append("")
        lines.append(f"(他{report['total_fired'] - len(report['alerts'])}銘柄も発火。上位のみ表示)")

    message = "\n".join(lines)
    if len(message) > MESSAGE_LIMIT:
        message = message[:MESSAGE_LIMIT] + "\n…(文字数上限のため省略)"
    return message


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
        cooldown=now_ms-int(previous.get("notified_at_ms",0)) < settings.state_alert_cooldown_minutes*60_000
        changed=facts!=tuple(previous.get("facts",[])) or abs(band-int(previous.get("band",-99)))>=2
        if cooldown and not changed:continue
        candidates.append(row)
    candidates.sort(key=lambda row:(row["features"].get("anomaly_score") or 0,row["features"].get("data_completeness_pct") or 0),reverse=True)
    candidates=candidates[:settings.state_alert_top_n]
    if not candidates:return None,updates
    lines=["🔬 **coin-scout 観測状態の重要変化**","異常度順（勝ちやすさ・方向予測ではありません）",""]
    for row in candidates:
        f=row["features"];flow=f.get("trade_imbalance_5m") or {};pos=f.get("high_low") or {}
        lines.append(f"**{row['symbol']}** / {row['observed_at_utc']} / 異常度 {f['anomaly_score']:.1f} / 充足度 {f['data_completeness_pct']:.0f}%")
        lines.append("観測: "+"、".join(row["observed_facts"]))
        lines.append(f"価格 5m {_pct(f.get('price_change_5m_pct'))} / 15m {_pct(f.get('price_change_15m_pct'))} / 1h {_pct(f.get('price_change_1h_pct'))} / 24h {_pct(f.get('price_change_24h_pct'))}")
        lines.append(f"数量OI 5m {_pct(f.get('oi_qty_change_5m_pct'))} / 15m {_pct(f.get('oi_qty_change_15m_pct'))} / 1h {_pct(f.get('oi_qty_change_1h_pct'))}")
        funding_z=f.get("funding_robust_z"); funding_text="蓄積中" if funding_z is None else f"robust-z {funding_z:+.2f} (n={f.get('funding_reference_samples')})"
        flow_text="取得不足" if not flow.get("coverage_complete") else f"{(flow.get('normalized_imbalance') or 0):+.2f} (B=買い手主導/A=売り手主導)"
        lines.append(f"Funding {funding_text} / 5m約定偏り {flow_text}")
        lines.append(f"1h高値から {_pct(pos.get('from_high_pct'))} / 1h安値から {_pct(pos.get('from_low_pct'))}")
        missing="、".join(row.get("missing_fields",[])) or "なし";lines.append(f"鮮度 {row.get('freshness_seconds') if row.get('freshness_seconds') is not None else '不明'}秒 / 欠測: {missing}")
        lines.append("次の観察: 数量OIと約定偏りの継続、高値・安値更新、欠測解消を次回実測で確認")
        lines.append("")
        updates[row["symbol"]]={"notified_at_ms":now_ms,"facts":row["observed_facts"],"band":int(f["anomaly_score"]//10),"event_id":row["event_id"]}
    message="\n".join(lines)
    return (message[:MESSAGE_LIMIT]+("\n…" if len(message)>MESSAGE_LIMIT else "")),updates
