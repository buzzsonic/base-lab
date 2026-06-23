from __future__ import annotations

from pathlib import Path
from typing import Any

from .analytics import PeriodWindow, account_ratio, from_ms_jst
from .models import AccountSnapshot, Position


DISCORD_LIMIT = 1900


def format_risk_message(snapshot: AccountSnapshot, risk: dict[str, Any]) -> str:
    if not snapshot.positions:
        return "【Hyperliquid Risk】現在ポジションなし。即時リスク通知対象なし。"

    lines = ["【Hyperliquid Risk Alert】"]
    for pos in snapshot.positions:
        ratio = account_ratio(pos.position_value, snapshot.account_value)
        lines.extend(
            [
                f"{pos.coin} {pos.side} {format_number(abs(pos.szi))}枚",
                f"建値 {format_price(pos.entry_px)} / 現在 {format_price(pos.mid_px)} / 含み損益 {format_signed_usd(pos.unrealized_pnl)}",
                f"口座 {format_usd(snapshot.account_value)} / 建玉 {format_usd(pos.position_value)} / 口座比 {ratio:.1f}倍",
                f"レバ {pos.leverage_type or 'unknown'} {format_number(pos.leverage_value)}x / 清算 {format_price(pos.liquidation_px)} / 距離 {format_pct(pos.liquidation_distance_pct)}",
            ]
        )
    lines.append(f"証拠金使用率: {risk['margin_usage_pct']:.1f}% / 注文: {len(snapshot.open_orders)}件")
    if risk["flags"]:
        lines.append("危険理由:")
        for item in risk["flags"][:6]:
            lines.append(f"- {item['detail']}")
    lines.append("判断: 追加禁止。ストップ未設定なら先に保護、清算距離が近いなら縮小/クローズ優先。")
    return "\n".join(lines)


def format_daily_report(window: PeriodWindow, snapshot: AccountSnapshot, stats: dict[str, Any], risk: dict[str, Any], score: dict[str, Any]) -> str:
    title = "【警告】Hyperliquid Daily Report" if score["total"] < 50 else "【Hyperliquid Daily Report】"
    lines = [
        title,
        f"対象: {window.start_jst.strftime('%Y-%m-%d %H:%M')} - {window.end_jst.strftime('%H:%M')} JST",
        f"今日の評価: {score['total']}/100 (PnL {score['pnl_score']}/50 / リスク {score['risk_score']}/50)",
        "",
        "■ 現在ポジション判断",
    ]
    lines.extend(format_position_judgement(snapshot, risk))
    lines.extend(
        [
            "",
            "■ 今日の成績",
            f"実現損益: {format_signed_usd(stats['realized_pnl'])}",
            f"手数料: -${stats['fees']:.2f}",
            f"概算ネット: {format_signed_usd(stats['net_pnl'])}",
            f"現在含み損益: {format_signed_usd(stats['unrealized_pnl'])}",
            "",
            f"約定数: {stats['fill_count']}回",
            f"ラウンドトリップ: {stats['round_trips']}回",
            f"勝敗: {stats['wins']}勝{stats['losses']}敗",
            f"勝率: {stats['win_rate']:.1f}%",
            f"平均利益: {format_signed_usd(stats['avg_win'])}",
            f"平均損失: {format_signed_usd(stats['avg_loss'])}",
            f"PF: {format_pf(stats['profit_factor'])}",
            "",
            "■ ロング/ショート別",
        ]
    )
    lines.extend(format_summary_rows(stats["side_summary"], include_hold=True))
    lines.append("")
    lines.append("■ 銘柄別")
    lines.extend(format_summary_rows(stats["coin_summary"], include_hold=True))
    lines.append("")
    lines.append("■ 保有時間別")
    lines.extend(format_summary_rows(stats["duration_summary"], include_hold=False))
    lines.append("")
    lines.append("■ ポジションサイズ別")
    lines.extend(format_summary_rows(stats["size_summary"], include_hold=False))
    lines.append("")
    lines.append("■ 減点項目")
    lines.extend(format_risk_flags(risk))
    lines.append("")
    lines.append("■ 明日のルール")
    lines.extend(build_next_rules(risk, stats, limit=3))
    return trim_for_discord("\n".join(lines))


def format_weekly_report(window: PeriodWindow, snapshot: AccountSnapshot, stats: dict[str, Any], risk: dict[str, Any], score: dict[str, Any]) -> str:
    positive = [row for row in stats["pattern_summary"] if row["net_pnl"] > 0][:3]
    negative = list(reversed([row for row in stats["pattern_summary"] if row["net_pnl"] < 0][-3:]))
    lines = [
        "【Hyperliquid Weekly Report】",
        f"対象: {window.start_jst.strftime('%Y-%m-%d %H:%M')} - {window.end_jst.strftime('%Y-%m-%d %H:%M')} JST",
        f"今週の評価: {score['total']}/100 (PnL {score['pnl_score']}/40 / 再現性 {score['reproducibility_score']}/30 / リスク {score['risk_score']}/30)",
        "",
        "■ 週間成績",
        f"実現損益: {format_signed_usd(stats['realized_pnl'])}",
        f"手数料: -${stats['fees']:.2f}",
        f"概算ネット: {format_signed_usd(stats['net_pnl'])}",
        f"約定数: {stats['fill_count']}回",
        f"ラウンドトリップ: {stats['round_trips']}回",
        f"勝敗: {stats['wins']}勝{stats['losses']}敗",
        f"勝率: {stats['win_rate']:.1f}%",
        f"平均利益: {format_signed_usd(stats['avg_win'])}",
        f"平均損失: {format_signed_usd(stats['avg_loss'])}",
        f"PF: {format_pf(stats['profit_factor'])}",
        "",
        "■ 勝ちパターン",
    ]
    lines.extend(format_pattern_rows(positive))
    lines.append("")
    lines.append("■ 負けパターン")
    lines.extend(format_pattern_rows(negative))
    lines.append("")
    lines.append("■ 銘柄別")
    lines.extend(format_summary_rows(stats["coin_summary"], include_hold=False))
    lines.append("")
    lines.append("■ 来週のルール")
    lines.extend(build_next_rules(risk, stats, limit=5))
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

