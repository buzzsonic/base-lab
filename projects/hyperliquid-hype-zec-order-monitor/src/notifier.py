from datetime import datetime
from typing import Any

import requests

from .logger import JST


DISCORD_CONTENT_LIMIT = 1900


class DiscordNotifyError(RuntimeError):
    pass


def format_report_message(report: dict[str, Any], settings: Any) -> str:
    run_at = datetime.fromisoformat(report["as_of_utc"]).astimezone(JST)
    header = [
        "【HYPE/ZEC未約定注文 15m監視】",
        f"時刻: {run_at.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"対象: 勝ち{settings.leaderboard_limit} / 負け{settings.leaderboard_limit} / {','.join(settings.target_symbols)}",
        f"判定: 近{settings.near_band_pct:g}% >= {format_usd(settings.min_near_change_usd)} / "
        f"{settings.watch_band_pct:g}%内 >= {format_usd(settings.min_watch_change_usd)}",
    ]

    stats = report["stats"]
    header.append(
        f"件数: 現在{stats['current_orders']} / 新規{stats['new_orders']} / "
        f"消滅{stats['cancelled_orders']} / 価格帯入り{stats['entered_watch_orders']}"
    )
    if not report["has_previous_snapshot"]:
        header.append("※ 初回は前回データなし。次回から変化判定")
        if not settings.notify_empty:
            return ""
        lines = header + ["", "初回スナップショットを保存しました。現在の3%内注文:"]
        active_rows = [row for row in report["active"] if row["alert"]]
        lines.extend(format_active_rows(active_rows[:6], settings))
        return clamp_message(lines)

    alert_rows = [row for row in report["changes"] if row["alert"]]
    active_rows = [row for row in report["active"] if row["alert"]]
    if not alert_rows:
        if not settings.notify_empty:
            return ""
        lines = header + ["", "変化アラートなし", "現在の3%内注文:"]
        lines.extend(format_active_rows(active_rows[:6], settings))
        return clamp_message(lines)

    lines = header + ["", "変化:"]
    lines.extend(format_change_rows(alert_rows[:8], settings))
    if active_rows:
        lines.append("")
        lines.append("現在の3%内:")
        lines.extend(format_active_rows(active_rows[:5], settings))
    return clamp_message(lines)


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


def format_change_rows(rows: list[dict[str, Any]], settings: Any) -> list[str]:
    lines = []
    for row in rows:
        label = f"{row['market']} {cohort_label(row['cohort'])}{row['side']}"
        near = f"近{settings.near_band_pct:g}% 新{format_usd(row['new_near_usd'])}/消{format_usd(row['cancelled_near_usd'])}"
        watch = f"{settings.watch_band_pct:g}% 新{format_usd(row['new_watch_usd'])}/消{format_usd(row['cancelled_watch_usd'])}"
        extra = []
        if row["entered_watch_usd"]:
            extra.append(f"帯入り{format_usd(row['entered_watch_usd'])}")
        if row["left_watch_usd"]:
            extra.append(f"帯抜け{format_usd(row['left_watch_usd'])}")
        price = price_range(row.get("watch_min_px"), row.get("watch_max_px"))
        suffix = f" / {row['wallet_count']}W / {price}"
        if extra:
            suffix += " / " + " ".join(extra)
        lines.append(f"- {label}: {near} / {watch}{suffix}")
    return lines


def format_active_rows(rows: list[dict[str, Any]], settings: Any) -> list[str]:
    if not rows:
        return ["なし"]
    lines = []
    for row in rows:
        label = f"{row['market']} {cohort_label(row['cohort'])}{row['side']}"
        lines.append(
            f"- {label}: 近{settings.near_band_pct:g}% {format_usd(row['near_usd'])} / "
            f"{settings.watch_band_pct:g}%内 {format_usd(row['watch_usd'])} "
            f"/ {row['wallet_count']}W / {price_range(row.get('watch_min_px'), row.get('watch_max_px'))}"
        )
    return lines


def clamp_message(lines: list[str]) -> str:
    while len("\n".join(lines)) > DISCORD_CONTENT_LIMIT and len(lines) > 6:
        lines.pop(-1)
    message = "\n".join(lines)
    if len(message) > DISCORD_CONTENT_LIMIT:
        return message[: DISCORD_CONTENT_LIMIT - 3] + "..."
    return message


def cohort_label(value: str) -> str:
    return {"winner": "勝ち", "loser": "負け"}.get(value, value)


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
