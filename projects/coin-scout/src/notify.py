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
        f"🔎 **coin-scout 狙い目スキャン** "
        f"{run_at_jst.strftime('%m/%d')}({WEEKDAYS_JA[run_at_jst.weekday()]}) "
        f"{run_at_jst.strftime('%H:%M')} JST"
    )
    sub = f"監視{report['watchlist_size']}銘柄(HL上場 ∩ CEX出来高$10M+)中 {report['total_fired']}銘柄が発火"

    lines = [header, sub, ""]

    for alert in report["alerts"]:
        chg = f"{alert['chg_pct']:+.1f}%" if alert["chg_pct"] is not None else "-"
        stars = "⭐" * alert["score"]
        lines.append(f"**{alert['coin']}** {format_price(alert['mark_px'])} ({chg}/24h) {stars}")
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
