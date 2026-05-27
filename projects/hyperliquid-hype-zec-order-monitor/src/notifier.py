from datetime import datetime
from typing import Any

import requests

from .logger import JST


DISCORD_CONTENT_LIMIT = 1900


class DiscordNotifyError(RuntimeError):
    pass


def format_report_message(report: dict[str, Any], settings: Any) -> str:
    run_at = datetime.fromisoformat(report["as_of_utc"]).astimezone(JST)
    stats = report["stats"]
    header = [
        "【HYPE/ZEC未約定注文 1h監視】",
        f"時刻: {run_at.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"対象: 勝ち{settings.leaderboard_limit} / 負け{settings.leaderboard_limit} / {','.join(settings.target_symbols)}",
        f"件数(参考): 現在{stats['current_orders']} / 新規{stats['new_orders']} / "
        f"消滅{stats['cancelled_orders']} / 価格帯入り{stats['entered_watch_orders']}",
    ]

    if not report["has_previous_snapshot"]:
        return ""

    decisions = build_decisions(report=report, settings=settings)
    if not settings.notify_empty and not should_notify(decisions):
        return ""

    lines = header + [""]
    if "HYPE" in settings.target_symbols:
        lines.extend(format_hype_section(decisions["HYPE"], settings))
        lines.append("")
    if "ZEC" in settings.target_symbols:
        lines.extend(format_zec_section(decisions["ZEC"], settings))

    return clamp_message(lines)


def build_decisions(report: dict[str, Any], settings: Any) -> dict[str, Any]:
    active_map = {(row["market"], row["cohort"], row["side"]): row for row in report["active"]}
    change_map = {(row["market"], row["cohort"], row["side"]): row for row in report["changes"]}
    decisions: dict[str, Any] = {}

    for market in settings.target_symbols:
        rows = {
            (cohort, side): merge_order_row(
                market=market,
                cohort=cohort,
                side=side,
                active=active_map.get((market, cohort, side)),
                change=change_map.get((market, cohort, side)),
            )
            for cohort in ("winner", "loser")
            for side in ("BUY", "SELL")
        }
        if market == "HYPE":
            decision, reason = judge_hype(rows=rows, settings=settings)
        elif market == "ZEC":
            decision, reason = judge_zec(rows=rows, settings=settings)
        else:
            decision, reason = "見送り", "判定ルール未設定"

        decisions[market] = {
            "market": market,
            "mid": (report.get("mids") or {}).get(market),
            "decision": decision,
            "reason": reason,
            "rows": rows,
            "has_actionable_signal": has_actionable_signal(rows=rows, decision=decision, settings=settings),
        }

    return decisions


def merge_order_row(
    market: str,
    cohort: str,
    side: str,
    active: dict[str, Any] | None,
    change: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "market": market,
        "cohort": cohort,
        "side": side,
        "near_usd": float((active or {}).get("near_usd") or 0),
        "watch_usd": float((active or {}).get("watch_usd") or 0),
        "wallet_count": int((active or {}).get("watch_wallet_count") or 0),
        "watch_min_px": (active or {}).get("watch_min_px"),
        "watch_max_px": (active or {}).get("watch_max_px"),
        "net_near_usd": float((change or {}).get("net_near_usd") or 0),
        "net_watch_usd": float((change or {}).get("net_watch_usd") or 0),
        "cancelled_near_usd": float((change or {}).get("cancelled_near_usd") or 0),
        "cancelled_watch_usd": float((change or {}).get("cancelled_watch_usd") or 0),
        "left_watch_usd": float((change or {}).get("left_watch_usd") or 0),
        "change_alert": bool((change or {}).get("alert")),
    }


def judge_hype(rows: dict[tuple[str, str], dict[str, Any]], settings: Any) -> tuple[str, str]:
    winner_buy = rows[("winner", "BUY")]
    loser_buy = rows[("loser", "BUY")]
    winner_sell = rows[("winner", "SELL")]
    loser_sell = rows[("loser", "SELL")]

    buy_near = winner_buy["near_usd"] + loser_buy["near_usd"]
    buy_watch = winner_buy["watch_usd"] + loser_buy["watch_usd"]
    buy_net_near = winner_buy["net_near_usd"] + loser_buy["net_near_usd"]
    buy_net_watch = winner_buy["net_watch_usd"] + loser_buy["net_watch_usd"]
    sell_watch = winner_sell["watch_usd"] + loser_sell["watch_usd"]
    buy_range = combined_price_range(winner_buy, loser_buy)

    buy_net_large_negative = buy_net_near <= -settings.min_near_change_usd or buy_net_watch <= -settings.min_watch_change_usd
    buy_thin = winner_buy["near_usd"] < 300_000 and loser_buy["near_usd"] < 300_000
    buy_removed = (
        winner_buy["cancelled_watch_usd"]
        + loser_buy["cancelled_watch_usd"]
        + winner_buy["left_watch_usd"]
        + loser_buy["left_watch_usd"]
    ) >= settings.min_near_change_usd

    if buy_thin:
        return "見送り", "勝ちBUY/負けBUYの近1%が両方薄い"
    if buy_net_large_negative:
        return "見送り", f"BUY netが大きくマイナス {format_signed_usd(min(buy_net_near, buy_net_watch))}"
    if buy_removed and buy_watch < 700_000:
        return "見送り", f"BUY消滅優勢、残存帯 {buy_range}"
    if buy_near >= 500_000 and buy_watch >= 700_000:
        if sell_watch >= buy_watch * 0.8:
            return "ロング待ち", "BUYは残るがSELL圧も同程度に強い"
        return "ロング可", f"BUYが近1% {format_usd(buy_near)} / 3% {format_usd(buy_watch)} 残存 {buy_range}"
    if buy_watch >= 500_000:
        return "ロング待ち", f"BUYは残るが近1%が弱い {buy_range}"
    return "見送り", "BUY残存が弱い"


def judge_zec(rows: dict[tuple[str, str], dict[str, Any]], settings: Any) -> tuple[str, str]:
    loser_sell = rows[("loser", "SELL")]
    winner_buy = rows[("winner", "BUY")]
    loser_buy = rows[("loser", "BUY")]
    sell_watch = loser_sell["watch_usd"]
    sell_net = loser_sell["net_watch_usd"]
    buy_watch = winner_buy["watch_usd"] + loser_buy["watch_usd"]

    if sell_watch >= settings.min_active_usd or sell_net >= settings.min_near_change_usd:
        return "踏み上げ警戒", "負けSELLが目立つ"
    if buy_watch < 300_000 and sell_watch < 300_000:
        return "弱い", "BUY/SELLとも薄い"
    return "見送り", "HYPE優先、ZECは決め手弱め"


def has_actionable_signal(rows: dict[tuple[str, str], dict[str, Any]], decision: str, settings: Any) -> bool:
    if decision in {"ロング可", "踏み上げ警戒"}:
        return True
    for row in rows.values():
        if row["change_alert"]:
            return True
        if abs(row["net_near_usd"]) >= settings.min_near_change_usd:
            return True
        if abs(row["net_watch_usd"]) >= settings.min_watch_change_usd:
            return True
    return False


def should_notify(decisions: dict[str, Any]) -> bool:
    return any(decision["has_actionable_signal"] for decision in decisions.values())


def format_hype_section(decision: dict[str, Any], settings: Any) -> list[str]:
    rows = decision["rows"]
    return [
        f"HYPE 現在: {format_price_with_dollar(decision['mid'])}",
        f"判定: {decision['decision']}",
        f"理由: {decision['reason']}",
        "",
        "■ BUY確認",
        format_detail_line("勝ちBUY", rows[("winner", "BUY")], settings),
        format_detail_line("負けBUY", rows[("loser", "BUY")], settings),
        "",
        "■ SELL圧",
        format_detail_line("勝ちSELL", rows[("winner", "SELL")], settings),
        format_detail_line("負けSELL", rows[("loser", "SELL")], settings),
    ]


def format_zec_section(decision: dict[str, Any], settings: Any) -> list[str]:
    rows = decision["rows"]
    return [
        f"ZEC 現在: {format_price_with_dollar(decision['mid'])}",
        f"判定: {decision['decision']} / {decision['reason']}",
        "BUY: "
        + format_short_line("勝ち", rows[("winner", "BUY")], settings)
        + " / "
        + format_short_line("負け", rows[("loser", "BUY")], settings),
        "SELL: "
        + format_short_line("勝ち", rows[("winner", "SELL")], settings)
        + " / "
        + format_short_line("負け", rows[("loser", "SELL")], settings),
    ]


def format_detail_line(label: str, row: dict[str, Any], settings: Any) -> str:
    return (
        f"{label}: active 近{settings.near_band_pct:g}% {format_usd(row['near_usd'])} / "
        f"{settings.watch_band_pct:g}% {format_usd(row['watch_usd'])} / "
        f"net近 {format_signed_usd(row['net_near_usd'])} / "
        f"net{settings.watch_band_pct:g}% {format_signed_usd(row['net_watch_usd'])} / "
        f"{row['wallet_count']}ウォレット / {price_range(row.get('watch_min_px'), row.get('watch_max_px'))}"
    )


def format_short_line(label: str, row: dict[str, Any], settings: Any) -> str:
    return (
        f"{label} active近 {format_usd(row['near_usd'])} / "
        f"{settings.watch_band_pct:g}% {format_usd(row['watch_usd'])} / "
        f"net{settings.watch_band_pct:g}% {format_signed_usd(row['net_watch_usd'])} / "
        f"{price_range(row.get('watch_min_px'), row.get('watch_max_px'))}"
    )


def combined_price_range(*rows: dict[str, Any]) -> str:
    min_values = [row.get("watch_min_px") for row in rows if row.get("watch_min_px") is not None]
    max_values = [row.get("watch_max_px") for row in rows if row.get("watch_max_px") is not None]
    if not min_values or not max_values:
        return "価格NA"
    return price_range(min(min_values), max(max_values))


def send_discord_message(webhook_url: str, message: str, dry_run: bool, logger: Any) -> None:
    if not message:
        logger.info("通知メッセージなし")
        return
    if dry_run:
        logger.info("DRY_RUN=true のためDiscord送信はスキップします。")
        logger.info(f"送信予定メッセージ:\n{message}")
        return

    try:
        response = requests.post(webhook_url, json={"content": message}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DiscordNotifyError(f"Discord Webhook送信に失敗しました: {exc}") from exc


def clamp_message(lines: list[str]) -> str:
    while len("\n".join(lines)) > DISCORD_CONTENT_LIMIT and len(lines) > 6:
        lines.pop(-1)
    message = "\n".join(lines)
    if len(message) > DISCORD_CONTENT_LIMIT:
        return message[: DISCORD_CONTENT_LIMIT - 3] + "..."
    return message


def format_usd(value: float | None) -> str:
    if value is None:
        return "NA"
    sign = "-" if value < 0 else ""
    value = abs(float(value))
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:,.0f}"


def format_signed_usd(value: float | None) -> str:
    if value is None:
        return "NA"
    sign = "+" if float(value) >= 0 else "-"
    return sign + format_usd(abs(float(value)))


def format_price_with_dollar(value: float | None) -> str:
    if value is None:
        return "$NA"
    return f"${format_price(value)}"


def format_price(value: float | None) -> str:
    if value is None:
        return "NA"
    value = float(value)
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


def price_range(min_px: float | None, max_px: float | None) -> str:
    if min_px is None or max_px is None:
        return "価格NA"
    if abs(min_px - max_px) < 1e-12:
        return f"@{format_price(min_px)}"
    return f"@{format_price(min_px)}-{format_price(max_px)}"
