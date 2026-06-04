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
        "【清算/OI監視 1h】",
        f"時刻: {run_at.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"対象: 勝ち{settings.leaderboard_limit} / 負け{settings.leaderboard_limit} / {','.join(settings.target_symbols)}",
        f"範囲: 清算候補 近{settings.liquidation_band_pct:g}% / OI前回比 / ポジション増減",
        f"件数(参考): ポジション{stats['current_positions']} / 清算候補{stats['liquidation_levels']} / errors={stats['errors']}",
        "注記: 清算量は監視ウォレット由来の推定。全市場の清算ヒートマップではありません。",
    ]

    if not report["has_previous_snapshot"]:
        return ""
    if not report.get("has_previous_market_contexts"):
        header.append("OI前回比: 前回データなし")
    if not report.get("has_previous_position_snapshot"):
        header.append("ポジション増減: 前回データなし")

    markets = build_market_summaries(report=report, settings=settings)
    if not settings.notify_empty and not should_notify(markets):
        return ""

    lines = header + [""]
    for market in settings.target_symbols:
        lines.extend(format_market_section(market, markets[market], settings))
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return clamp_message(lines)


def build_market_summaries(report: dict[str, Any], settings: Any) -> dict[str, Any]:
    position_change_map = {(row["market"], row["cohort"]): row for row in report.get("position_changes", [])}
    market_rows = report.get("markets") or {}
    liquidation_levels = report.get("liquidation_levels") or {}
    summaries: dict[str, Any] = {}

    for market in settings.target_symbols:
        position_changes = {
            cohort: merge_position_change_row(
                market=market,
                cohort=cohort,
                row=position_change_map.get((market, cohort)),
            )
            for cohort in ("winner", "loser")
        }
        market_row = merge_market_row(market=market, row=market_rows.get(market))
        levels = liquidation_levels.get(market, {"above": [], "below": []})

        summaries[market] = {
            "market": market,
            "market_row": market_row,
            "liquidation_levels": levels,
            "position_changes": position_changes,
            "has_actionable_signal": has_actionable_signal(
                market_row=market_row,
                liquidation_levels=levels,
                position_changes=position_changes,
                settings=settings,
            ),
        }

    return summaries


def merge_market_row(market: str, row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "market": market,
        "mark_px": (row or {}).get("mark_px"),
        "open_interest_usd": (row or {}).get("open_interest_usd"),
        "oi_delta_usd": (row or {}).get("oi_delta_usd"),
        "oi_delta_pct": (row or {}).get("oi_delta_pct"),
        "funding": (row or {}).get("funding"),
        "oi_alert": bool((row or {}).get("oi_alert")),
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


def has_actionable_signal(
    market_row: dict[str, Any],
    liquidation_levels: dict[str, list[dict[str, Any]]],
    position_changes: dict[str, dict[str, Any]],
    settings: Any,
) -> bool:
    if market_row["oi_alert"]:
        return True
    for row in position_changes.values():
        if row["alert"]:
            return True
    for rows in liquidation_levels.values():
        for row in rows:
            if row.get("alert"):
                return True
    return False


def should_notify(markets: dict[str, Any]) -> bool:
    return any(summary["has_actionable_signal"] for summary in markets.values())


def format_market_section(market: str, summary: dict[str, Any], settings: Any) -> list[str]:
    market_row = summary["market_row"]
    position_changes = summary["position_changes"]
    levels = summary["liquidation_levels"]
    return [
        f"{market} 現在: {format_price_with_dollar(market_row['mark_px'])}",
        (
            f"OI: {format_usd(market_row['open_interest_usd'])} / "
            f"前回比 {format_signed_usd(market_row['oi_delta_usd'])} "
            f"({format_signed_pct(market_row['oi_delta_pct'])}) / "
            f"Funding {format_funding(market_row['funding'])}"
        ),
        format_liquidation_side_line("上", "ショート清算", levels.get("above", []), settings),
        format_liquidation_side_line("下", "ロング清算", levels.get("below", []), settings),
        f"見方: {format_interpretation(market_row=market_row, levels=levels, settings=settings)}",
        (
            "ポジ増減: "
            f"勝ち {format_position_change_compact(position_changes['winner'])} / "
            f"負け {format_position_change_compact(position_changes['loser'])}"
        ),
    ]


def format_liquidation_side_line(label: str, liquidation_label: str, levels: list[dict[str, Any]], settings: Any) -> str:
    visible = [row for row in levels if float(row.get("notional_usd") or 0) >= settings.min_liquidation_usd]
    if not visible:
        return f"{label}: {liquidation_label} 近{settings.liquidation_band_pct:g}%なし"

    parts = [format_liquidation_level(row) for row in visible[: settings.max_liquidation_levels]]
    omitted = len(visible) - len(parts)
    suffix = f" 他{omitted}" if omitted > 0 else ""
    return f"{label}: {liquidation_label} " + " / ".join(parts) + suffix


def format_liquidation_level(row: dict[str, Any]) -> str:
    return (
        f"@{format_price(row.get('bucket_px'))} "
        f"({format_pct(row.get('avg_distance_pct'))}) "
        f"{format_usd(row.get('notional_usd'))}/{int(row.get('wallet_count') or 0)}W"
    )


def format_interpretation(market_row: dict[str, Any], levels: dict[str, list[dict[str, Any]]], settings: Any) -> str:
    above_total = sum(float(row.get("notional_usd") or 0) for row in levels.get("above", []) if row.get("alert"))
    below_total = sum(float(row.get("notional_usd") or 0) for row in levels.get("below", []) if row.get("alert"))
    oi_delta = market_row.get("oi_delta_usd")

    comments: list[str] = []
    if oi_delta is None:
        comments.append("OI前回比NA")
    elif abs(float(oi_delta)) >= settings.min_oi_delta_usd:
        comments.append("OI増で燃料追加" if float(oi_delta) > 0 else "OI減で燃料低下")
    else:
        comments.append("OI変化小")

    if above_total >= settings.min_liquidation_usd and below_total >= settings.min_liquidation_usd:
        if above_total >= below_total * 1.5:
            comments.append("上側ショート清算が厚い")
        elif below_total >= above_total * 1.5:
            comments.append("下側ロング清算が厚い")
        else:
            comments.append("上下に清算燃料")
    elif above_total >= settings.min_liquidation_usd:
        comments.append("上昇時は表示価格超えで買い戻し加速警戒")
    elif below_total >= settings.min_liquidation_usd:
        comments.append("下落時は表示価格割れで投げ加速警戒")
    else:
        comments.append(f"近{settings.liquidation_band_pct:g}%の清算帯は薄い")

    return " / ".join(comments)


def format_position_change_compact(row: dict[str, Any]) -> str:
    return (
        f"net {format_signed_usd(row['net_delta_usd'])}, "
        f"L {format_signed_usd(row['long_delta_usd'])}, "
        f"S {format_signed_usd(row['short_delta_usd'])}, {row['wallet_count']}W"
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


def format_signed_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{float(value) * 100:+.2f}%"


def format_funding(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{float(value) * 100:+.4f}%"


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
