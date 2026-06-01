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
        "【HYPE/ZEC売買判断 1h】",
        f"時刻: {run_at.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"対象: 勝ち{settings.leaderboard_limit} / 負け{settings.leaderboard_limit} / {','.join(settings.target_symbols)}",
        f"件数(参考): 注文{stats['current_orders']} / ポジション{stats['current_positions']} / "
        f"注文変化 新{stats['new_orders']} 消{stats['cancelled_orders']}",
    ]
    if report["has_previous_snapshot"] and not report.get("has_previous_position_snapshot"):
        header.append("ポジション増減: 前回データなし")

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
    position_map = {(row["market"], row["cohort"]): row for row in report.get("positions", [])}
    position_change_map = {(row["market"], row["cohort"]): row for row in report.get("position_changes", [])}
    signals = report.get("signals") or {}
    decisions: dict[str, Any] = {}

    for market in settings.target_symbols:
        order_rows = {
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
        positions = {
            cohort: merge_position_row(market=market, cohort=cohort, row=position_map.get((market, cohort)))
            for cohort in ("winner", "loser")
        }
        position_changes = {
            cohort: merge_position_change_row(
                market=market,
                cohort=cohort,
                row=position_change_map.get((market, cohort)),
            )
            for cohort in ("winner", "loser")
        }
        signal = signals.get(market, {"symbol": market, "action": "判定不可"})
        decision, reason = judge_signal(market=market, signal=signal, position_changes=position_changes)

        decisions[market] = {
            "market": market,
            "mid": (report.get("mids") or {}).get(market),
            "decision": decision,
            "reason": reason,
            "signal": signal,
            "order_rows": order_rows,
            "positions": positions,
            "position_changes": position_changes,
            "has_actionable_signal": has_actionable_signal(
                order_rows=order_rows,
                position_changes=position_changes,
                decision=decision,
                settings=settings,
            ),
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


def merge_position_row(market: str, cohort: str, row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "market": market,
        "cohort": cohort,
        "long_usd": float((row or {}).get("long_usd") or 0),
        "short_usd": float((row or {}).get("short_usd") or 0),
        "net_usd": float((row or {}).get("net_usd") or 0),
        "long_avg_entry": (row or {}).get("long_avg_entry"),
        "short_avg_entry": (row or {}).get("short_avg_entry"),
        "long_wallet_count": int((row or {}).get("long_wallet_count") or 0),
        "short_wallet_count": int((row or {}).get("short_wallet_count") or 0),
    }


def merge_position_change_row(market: str, cohort: str, row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "market": market,
        "cohort": cohort,
        "long_delta_usd": float((row or {}).get("long_delta_usd") or 0),
        "short_delta_usd": float((row or {}).get("short_delta_usd") or 0),
        "net_delta_usd": float((row or {}).get("net_delta_usd") or 0),
        "wallet_count": int((row or {}).get("wallet_count") or 0),
        "alert": bool((row or {}).get("alert")),
    }


def judge_signal(
    market: str,
    signal: dict[str, Any],
    position_changes: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    action = str(signal.get("action") or "判定不可")
    if action == "判定不可":
        return action, str(signal.get("reason") or "SMAデータ不足")

    winner_net = position_changes["winner"]["net_delta_usd"]
    loser_net = position_changes["loser"]["net_delta_usd"]
    if market == "HYPE":
        if action == "ロング":
            if winner_net < 0:
                return action, f"SMAはロング、ただし勝ちnet減少 {format_signed_usd(winner_net)}"
            return action, "SMA6がSMA12を上回る"
        return action, "SMA6がSMA12以下"

    if market == "ZEC":
        if action == "ロング":
            return action, "SMA6がSMA24を上回る"
        if action == "ショート":
            if winner_net > 0:
                return action, f"SMAはショート、ただし勝ちnet増加 {format_signed_usd(winner_net)}"
            return action, "SMA6がSMA24を下回る"
    return action, f"勝ちnet {format_signed_usd(winner_net)} / 負けnet {format_signed_usd(loser_net)}"


def has_actionable_signal(
    order_rows: dict[tuple[str, str], dict[str, Any]],
    position_changes: dict[str, dict[str, Any]],
    decision: str,
    settings: Any,
) -> bool:
    if decision in {"ロング", "ショート"}:
        return True
    for row in position_changes.values():
        if row["alert"]:
            return True
    for row in order_rows.values():
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
    return format_market_section("HYPE", decision, settings)


def format_zec_section(decision: dict[str, Any], settings: Any) -> list[str]:
    return format_market_section("ZEC", decision, settings)


def format_market_section(market: str, decision: dict[str, Any], settings: Any) -> list[str]:
    positions = decision["positions"]
    position_changes = decision["position_changes"]
    return [
        f"{market} {format_price_with_dollar(decision['mid'])}",
        f"判断: {decision['decision']}",
        f"条件: {format_signal_condition(market, decision['signal'])}",
        f"出る/切替: {decision['signal'].get('exit_rule') or 'NA'}",
        f"理由: {decision['reason']}",
        "",
        "■ ポジション増減",
        format_position_change_line("勝ち", position_changes["winner"]),
        format_position_change_line("負け", position_changes["loser"]),
        "",
        "■ 現在ポジ",
        format_position_line("勝ち", positions["winner"]),
        format_position_line("負け", positions["loser"]),
        format_order_summary(decision["order_rows"], settings),
    ]


def format_signal_condition(market: str, signal: dict[str, Any]) -> str:
    sma6 = signal.get("sma6")
    compare_key = "sma12" if market == "HYPE" else "sma24"
    compare_label = "SMA12" if market == "HYPE" else "SMA24"
    compare = signal.get(compare_key)
    if sma6 is None or compare is None:
        return "SMAデータ不足"
    mark = ">" if sma6 > compare else "<" if sma6 < compare else "="
    return f"SMA6 {format_price_with_dollar(sma6)} {mark} {compare_label} {format_price_with_dollar(compare)} / 6h {format_pct(signal.get('ret6h'))}"


def format_position_change_line(label: str, row: dict[str, Any]) -> str:
    return (
        f"{label}: net {format_signed_usd(row['net_delta_usd'])} / "
        f"Long側 {format_signed_usd(row['long_delta_usd'])} / "
        f"Short側 {format_signed_usd(row['short_delta_usd'])} / {row['wallet_count']}W"
    )


def format_position_line(label: str, row: dict[str, Any]) -> str:
    return (
        f"{label}: Long {format_usd(row['long_usd'])} avg {format_price_with_dollar(row['long_avg_entry'])} "
        f"({row['long_wallet_count']}W) / Short {format_usd(row['short_usd'])} "
        f"avg {format_price_with_dollar(row['short_avg_entry'])} ({row['short_wallet_count']}W)"
    )


def format_order_summary(rows: dict[tuple[str, str], dict[str, Any]], settings: Any) -> str:
    buy_rows = [rows[("winner", "BUY")], rows[("loser", "BUY")]]
    sell_rows = [rows[("winner", "SELL")], rows[("loser", "SELL")]]
    return (
        "注文補足: "
        f"BUY近 {format_usd(sum(row['near_usd'] for row in buy_rows))} / "
        f"{settings.watch_band_pct:g}% {format_usd(sum(row['watch_usd'] for row in buy_rows))} / "
        f"net{settings.watch_band_pct:g} {format_signed_usd(sum(row['net_watch_usd'] for row in buy_rows))} | "
        f"SELL近 {format_usd(sum(row['near_usd'] for row in sell_rows))} / "
        f"{settings.watch_band_pct:g}% {format_usd(sum(row['watch_usd'] for row in sell_rows))} / "
        f"net{settings.watch_band_pct:g} {format_signed_usd(sum(row['net_watch_usd'] for row in sell_rows))}"
    )


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


def format_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{float(value) * 100:+.1f}%"


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
