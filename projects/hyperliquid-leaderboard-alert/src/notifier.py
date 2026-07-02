from datetime import datetime
from typing import Any

from shared.discord import DiscordNotifyError, send_discord_message  # noqa: F401


DISCORD_CONTENT_LIMIT = 1900


def format_position_report_message(report: dict[str, Any], run_at_jst: datetime, settings: Any) -> str:
    stats = report["stats"]
    header = [
        "【Hyperliquidリーダーボード集約】",
        f"時刻: {run_at_jst.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"対象: 勝ち{settings.leaderboard_limit} / 負け{settings.leaderboard_limit}",
        f"条件: 現在>={format_usd(settings.min_abs_position_usd)} / 新規・増加>={format_usd(settings.min_position_change_usd)}",
        f"件数: 現在{stats['current_positions']} / 新規{stats['new_positions']} / 増加{stats['increased_positions']}",
        "",
    ]
    if not report["has_previous_snapshot"]:
        header.append("※ 初回は前回データがないため、新規・増加は次回から判定")
        header.append("")

    current_limit = 4
    change_limit = 3
    while current_limit >= 1:
        lines = header + _format_cohort_sections(report, current_limit=current_limit, change_limit=change_limit)
        message = "\n".join(lines)
        if len(message) <= DISCORD_CONTENT_LIMIT:
            return message
        if change_limit > 1:
            change_limit -= 1
        else:
            current_limit -= 1

    compact_lines = header + _format_cohort_sections(report, current_limit=1, change_limit=1)
    return "\n".join(compact_lines)[:DISCORD_CONTENT_LIMIT]


def _format_cohort_sections(report: dict[str, Any], current_limit: int, change_limit: int) -> list[str]:
    lines: list[str] = []
    for cohort, label in [("winner", "勝ちウォレット"), ("loser", "負けウォレット")]:
        lines.append(f"■ {label} 現在ポジ")
        lines.extend(_format_summary_rows(report["current_summary"], cohort=cohort, limit=current_limit, mode="current"))
        lines.append(f"■ {label} 新規ポジ")
        lines.extend(_format_summary_rows(report["new_summary"], cohort=cohort, limit=change_limit, mode="new"))
        lines.append(f"■ {label} 増加ポジ")
        lines.extend(_format_summary_rows(report["increased_summary"], cohort=cohort, limit=change_limit, mode="increase"))
        lines.append("")
    return lines


def _format_summary_rows(rows: list[dict[str, Any]], cohort: str, limit: int, mode: str) -> list[str]:
    selected = [row for row in rows if row["cohort"] == cohort][:limit]
    if not selected:
        return ["なし"]

    lines = []
    for row in selected:
        side = _side_label(row["side"])
        if mode == "current":
            lines.append(
                f"{row['coin']} {side} {format_usd(row['total_usd'])} / "
                f"Entry {format_price(row['avg_entry_px'])} / 現在 {format_price(row.get('current_px'))} / "
                f"{row['wallet_count']}ウォレット / PnL {format_usd(row.get('unrealized_pnl'))}"
            )
        elif mode == "new":
            lines.append(
                f"{row['coin']} {side} 新規 {format_usd(row['total_usd'])} / "
                f"Entry {format_price(row['avg_entry_px'])} / {row['wallet_count']}ウォレット"
            )
        else:
            lines.append(
                f"{row['coin']} {side} 増加 +{format_usd(row['total_usd'])} / "
                f"推定Entry {format_price(row['avg_entry_px'])} / {row['wallet_count']}ウォレット"
            )

    omitted = len([row for row in rows if row["cohort"] == cohort]) - len(selected)
    if omitted > 0:
        lines.append(f"...ほか{omitted}行")
    return lines


def _side_label(side: str) -> str:
    return {"long": "LONG", "short": "SHORT"}.get(side, side.upper())


def format_usd(value: float | None) -> str:
    if value is None:
        return "取得不可"
    sign = "-" if value < 0 else ""
    value = abs(float(value))
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:,.0f}"


def format_price(value: float | None) -> str:
    if value is None:
        return "取得不可"
    if abs(value) >= 1000:
        return f"${value:,.2f}"
    return f"${value:.6g}"


def format_number(value: float | None) -> str:
    if value is None:
        return "取得不可"
    return f"{value:,.6g}"
