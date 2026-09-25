from __future__ import annotations

from pathlib import Path
from typing import Any

from .analytics import PeriodWindow, account_ratio, from_ms_jst
from .models import AccountSnapshot, Position


DISCORD_LIMIT = 1900


def format_behavior_risk_message(snapshot: AccountSnapshot, events: list[dict[str, Any]], equity: dict[str, float], level: str) -> str:
    icons = {"YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴", "CRITICAL": "🚨"}
    names = {"SIZE_UP_AFTER_WIN": "勝ち後サイズ急増", "REVENGE_TRADE": "損失後ドテン",
             "LOSS_AVERAGING": "含み損で追加", "PROFIT_PYRAMIDING": "利益中に急増",
             "DAILY_PROFIT_GIVEBACK": "利益吐き出し", "PEAK_DRAWDOWN": "ピークDD",
             "SAME_COIN_OVERTRADE": "同一銘柄を回転", "CONSECUTIVE_LOSSES": "連敗",
             "LIQUIDATION_TOO_CLOSE": "清算接近", "OVERSIZED_POSITION": "建玉過大",
             "DAILY_LOSS_LIMIT": "日次損失上限"}
    counts: dict[tuple[str, str | None], int] = {}
    levels: dict[tuple[str, str | None], str] = {}
    for event in events:
        key = (event["risk_type"], event.get("coin"))
        counts[key] = counts.get(key, 0) + 1
        levels[key] = event["level"]
    position_label = " / ".join(f"{p.coin} {p.side}" for p in snapshot.positions) or "ポジションなし"
    lines = [f"{icons.get(level, '⚠️')} {level}｜{position_label}", ""]
    if snapshot.positions:
        for pos in snapshot.positions:
            ratio = account_ratio(pos.position_value, snapshot.account_value)
            one_pct = pos.position_value * .01
            lines.extend([
                f"💰 ${snapshot.account_value:,.0f}｜📦 ${pos.position_value:,.0f}（{ratio:.1f}x）",
                f"⚡ 1%逆行 -${one_pct:,.2f}（-{(one_pct / snapshot.account_value * 100 if snapshot.account_value else 0):.1f}%）｜📈 {format_signed_usd(pos.unrealized_pnl)}",
            ])
    lines.extend([
        f"🏁 開始 ${equity['start']:,.0f}｜最高 ${equity['peak']:,.0f}｜DD -{equity['drawdown_pct']:.1f}%", "",
    ])
    for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]:
        kind, coin = key; mark = icons.get(levels[key], "⚠️"); suffix = f" ×{count}" if count > 1 else ""
        lines.append(f"{mark} {names.get(kind, kind)}{f'（{coin}）' if coin else ''}{suffix}")
    lines.extend(["", "🛑 追加しない｜サイズ縮小｜損失上限を確認"])
    return "\n".join(lines)[:DISCORD_LIMIT]


def format_risk_message(snapshot: AccountSnapshot, risk: dict[str, Any]) -> str:
    if not snapshot.positions:
        return "【Hyperliquid Risk】現在ポジションなし。即時リスク通知対象なし。"

    lines = ["🟠 ORANGE｜" + " / ".join(f"{p.coin} {p.side}" for p in snapshot.positions), ""]
    for pos in snapshot.positions:
        ratio = account_ratio(pos.position_value, snapshot.account_value)
        one_pct = pos.position_value * .01
        lines.extend(
            [
                f"💰 {format_usd(snapshot.account_value)}｜📦 {format_usd(pos.position_value)}（{ratio:.1f}x）",
                f"⚡ 1%逆行 -${one_pct:.2f}（-{(one_pct / snapshot.account_value * 100 if snapshot.account_value else 0):.1f}%）｜📈 {format_signed_usd(pos.unrealized_pnl)}",
            ]
        )
    lines.append("")
    if risk["flags"]:
        for item in risk["flags"][:6]:
            lines.append(f"🟠 {item['detail']}")
    lines.append("")
    lines.append("🛑 追加しない｜保護注文を確認｜必要なら縮小")
    return "\n".join(lines)


def format_daily_report(window: PeriodWindow, snapshot: AccountSnapshot, stats: dict[str, Any], risk: dict[str, Any], score: dict[str, Any]) -> str:
    title = "🔴 DAILY REPORT" if stats["net_pnl"] < 0 else "🟢 DAILY REPORT"
    best = stats["coin_summary"][0] if stats["coin_summary"] else None
    worst = stats["coin_summary"][-1] if stats["coin_summary"] else None
    lines = [
        title,
        f"{window.label}｜評価 {score['total']}/100", "",
        f"💰 純損益 {format_signed_usd(stats['net_pnl'])}｜手数料 -${stats['fees']:.2f}",
        f"🎯 {stats['wins']}勝{stats['losses']}敗｜勝率 {stats['win_rate']:.0f}%｜PF {format_pf(stats['profit_factor'])}",
        f"📊 平均利益 {format_signed_usd(stats['avg_win'])}｜平均損失 {format_signed_usd(stats['avg_loss'])}",
        "",
        f"🏆 最大貢献 {best['label']} {format_signed_usd(best['net_pnl'])}" if best else "🏆 取引なし",
        f"📉 最大損失 {worst['label']} {format_signed_usd(worst['net_pnl'])}" if worst else "",
        "", "⚠️ 現在",
    ]
    lines.extend(format_position_judgement(snapshot, risk)[:2])
    lines.extend(["", "🛑 明日のルール"] + build_next_rules(risk, stats, limit=3))
    return trim_for_discord("\n".join(lines))


def format_weekly_report(window: PeriodWindow, snapshot: AccountSnapshot, stats: dict[str, Any], risk: dict[str, Any], score: dict[str, Any]) -> str:
    positive = [row for row in stats["pattern_summary"] if row["net_pnl"] > 0][:3]
    negative = list(reversed([row for row in stats["pattern_summary"] if row["net_pnl"] < 0][-3:]))
    lines = [
        "📅 WEEKLY REPORT",
        f"{window.start_jst.strftime('%m/%d')}–{window.end_jst.strftime('%m/%d')}｜評価 {score['total']}/100", "",
        f"💰 純損益 {format_signed_usd(stats['net_pnl'])}｜手数料 -${stats['fees']:.2f}",
        f"🎯 {stats['wins']}勝{stats['losses']}敗｜勝率 {stats['win_rate']:.0f}%｜PF {format_pf(stats['profit_factor'])}",
        f"📊 平均利益 {format_signed_usd(stats['avg_win'])}｜平均損失 {format_signed_usd(stats['avg_loss'])}",
        "", "🟢 勝ちパターン",
    ]
    lines.extend(format_pattern_rows(positive))
    lines.append("")
    lines.append("🔴 負けパターン")
    lines.extend(format_pattern_rows(negative))
    lines.append("")
    lines.append("🛑 来週の3ルール")
    lines.extend(build_next_rules(risk, stats, limit=3))
    return trim_for_discord("\n".join(lines))


def write_report(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message + "\n", encoding="utf-8")


def format_position_judgement(snapshot: AccountSnapshot, risk: dict[str, Any]) -> list[str]:
    if not snapshot.positions:
        return ["現在ポジションなし。"]
    lines: list[str] = []
    for pos in snapshot.positions:
        ratio = account_ratio(pos.position_value, snapshot.account_value)
        lines.append(
            f"{pos.coin} {pos.side}: 建玉 {format_usd(pos.position_value)} / 口座比 {ratio:.1f}倍 / "
            f"含み損益 {format_signed_usd(pos.unrealized_pnl)} / 清算距離 {format_pct(pos.liquidation_distance_pct)}"
        )
    if risk["flags"]:
        lines.append("判断: 追加禁止。ストップ未設定なら先に保護。清算距離が近い/証拠金使用率が高いなら縮小優先。")
    else:
        lines.append("判断: 現時点の強いリスク警告はなし。利益を伸ばす場合もストップは維持。")
    return lines


def format_summary_rows(rows: list[dict[str, Any]], include_hold: bool) -> list[str]:
    if not rows:
        return ["なし"]
    lines = []
    for row in rows[:8]:
        line = (
            f"{row['label']}: {row['wins']}勝{row['losses']}敗 / "
            f"{format_signed_usd(row['net_pnl'])} / 勝率{row['win_rate']:.1f}%"
        )
        if include_hold and row.get("avg_hold_minutes") is not None:
            line += f" / 平均保有{format_minutes(row['avg_hold_minutes'])}"
        lines.append(line)
    return lines


def format_pattern_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["なし"]
    return [
        f"{idx}. {row['label']} {row['wins']}勝{row['losses']}敗 / {format_signed_usd(row['net_pnl'])} / 勝率{row['win_rate']:.1f}%"
        for idx, row in enumerate(rows[:3], start=1)
    ]


def format_risk_flags(risk: dict[str, Any]) -> list[str]:
    if not risk["flags"]:
        return ["なし"]
    return [f"{item['name']}: あり ({item['detail']})" for item in risk["flags"][:8]]


def build_next_rules(risk: dict[str, Any], stats: dict[str, Any], limit: int) -> list[str]:
    rules: list[str] = []
    names = {item["name"] for item in risk["flags"]}
    if "口座比6倍以上" in names:
        rules.append("口座比6倍以上は禁止")
    if "ストップなし" in names:
        rules.append("建てた直後に損切り注文を置く")
    if "損失後の即反転" in names:
        rules.append("損失後60分以内の逆方向エントリー禁止")
    if "清算あり" in names:
        rules.append("清算後24時間は新規エントリー禁止")
    if stats["fees"] > 0 and stats["gross_profit"] > 0 and stats["fees"] / stats["gross_profit"] >= 0.30:
        rules.append("手数料負けしやすい短期回転を減らす")
    if not rules:
        rules.append("口座比3倍以内を維持")
        rules.append("含み益が出たらストップを建値側へ寄せる")
        rules.append("根拠が薄い短期回転を避ける")
    return [f"{idx}. {rule}" for idx, rule in enumerate(rules[:limit], start=1)]


def trim_for_discord(message: str) -> str:
    if len(message) <= DISCORD_LIMIT:
        return message
    suffix = "\n...文字数制限のため一部省略"
    return message[: DISCORD_LIMIT - len(suffix)] + suffix


def format_usd(value: float | None) -> str:
    if value is None:
        return "取得不可"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:.2f}"


def format_signed_usd(value: float | None) -> str:
    if value is None:
        return "取得不可"
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(float(value)):.2f}"


def format_price(value: float | None) -> str:
    if value is None:
        return "取得不可"
    if abs(value) >= 100:
        return f"${value:,.3f}"
    if abs(value) >= 1:
        return f"${value:.5g}"
    return f"${value:.6g}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "取得不可"
    return f"{value:.2f}%"


def format_number(value: float | None) -> str:
    if value is None:
        return "取得不可"
    return f"{value:,.6g}"


def format_pf(value: float) -> str:
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}"


def format_minutes(minutes: float) -> str:
    if minutes < 60:
        return f"{minutes:.0f}分"
    hours = int(minutes // 60)
    rest = int(minutes % 60)
    return f"{hours}時間{rest}分"
