from datetime import datetime
from typing import Any

import requests

from .leaderboard import short_address


DISCORD_CONTENT_LIMIT = 1900


class DiscordNotifyError(RuntimeError):
    pass


def format_alert_message(alerts: list[dict[str, Any]], run_at_jst: datetime, settings: Any) -> str:
    header = [
        "【Hyperliquidリーダーボード検知】",
        f"実行時刻: {run_at_jst.strftime('%Y-%m-%d %H:%M:%S JST')}",
        f"条件: ポジションUSD換算 >= {format_usd(settings.min_abs_position_usd)} / 方向={_target_side_label(settings.target_side)}",
        f"通知対象: {len(alerts)}件",
        "",
    ]

    visible_alerts = alerts[:10]
    while visible_alerts:
        omitted_count = max(len(alerts) - len(visible_alerts), 0)
        lines = header + _format_alert_lines(visible_alerts, omitted_count)
        message = "\n".join(lines)
        if len(message) <= DISCORD_CONTENT_LIMIT:
            return message
        visible_alerts = visible_alerts[:-1]

    return "\n".join(header + ["通知対象が多すぎるため本文を省略しました。GitHub Actionsログを確認してください。"])


def send_discord_message(webhook_url: str, message: str, dry_run: bool, logger: Any) -> None:
    if dry_run:
        logger.info("DRY_RUN=true のためDiscord送信はスキップします。")
        logger.info(f"送信予定メッセージ:\n{message}")
        return

    try:
        response = requests.post(webhook_url, json={"content": message}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DiscordNotifyError(f"Discord Webhook送信に失敗しました: {exc}") from exc


def _format_alert_lines(alerts: list[dict[str, Any]], omitted_count: int) -> list[str]:
    lines: list[str] = []
    for index, alert in enumerate(alerts, start=1):
        wallet = alert["wallet"]
        display_name = wallet.get("display_name")
        name_part = f" ({display_name})" if display_name else ""
        leverage = _format_leverage(alert.get("leverage_value"), alert.get("leverage_type"))
        lines.extend(
            [
                f"{index}. {wallet['cohort_label']} #{wallet['rank']} {short_address(wallet['address'])}{name_part}",
                f"   銘柄: {alert['coin']} / {_side_label(alert['side'])}{leverage}",
                f"   ポジション: {format_usd(alert['abs_position_usd'])} / 数量 {format_number(alert['abs_size'])}",
                f"   Entry: {format_price(alert.get('entry_px'))} / 未実現PnL: {format_usd(alert.get('unrealized_pnl'))} / Liq: {format_price(alert.get('liquidation_px'))}",
            ]
        )
    if omitted_count:
        lines.append(f"...ほか {omitted_count} 件はDiscord文字数制限のため省略")
    return lines


def _side_label(side: str) -> str:
    return {"long": "ロング", "short": "ショート"}.get(side, side)


def _target_side_label(side: str) -> str:
    return {"both": "両方", "long": "ロングのみ", "short": "ショートのみ"}.get(side, side)


def _format_leverage(value: float | None, leverage_type: str | None) -> str:
    if value is None:
        return ""
    type_label = f"{leverage_type} " if leverage_type else ""
    return f" / {type_label}{value:g}x"


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
