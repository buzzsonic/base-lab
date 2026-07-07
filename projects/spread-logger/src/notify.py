"""アラート判定(閾値+クールダウン)とDiscordメッセージの整形。事実の報告のみ、売買推奨はしない。"""

from datetime import datetime
from typing import Any

from .config import Settings
from .state import is_alert_in_cooldown, mark_alert_fired

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def evaluate_alerts(
    coins: tuple[str, ...],
    metrics: dict[str, Any],
    settings: Settings,
    state: dict[str, Any],
    now_jst: datetime,
) -> list[dict[str, Any]]:
    """閾値超え、かつクールダウン中でないアラートの一覧を返す(まだstateには書き込まない)。"""
    alerts: list[dict[str, Any]] = []

    for coin in coins:
        m = metrics["per_coin"].get(coin, {})

        dev = m.get("effective_usdjpy_dev_pct")
        if dev is not None and abs(dev) >= settings.effective_jpy_dev_alert_pct:
            key = f"effective_jpy:{coin}"
            if not is_alert_in_cooldown(state, key, now_jst, settings.alert_cooldown_hours):
                alerts.append(
                    {
                        "key": key,
                        "text": (
                            f"実効ドル円乖離 **{coin}** {dev:+.2f}% "
                            f"(実効{m['effective_usdjpy']:.2f}円 / 参照レート比)"
                        ),
                    }
                )

        cross = m.get("domestic_cross_pct")
        if cross is not None and cross >= settings.domestic_cross_alert_pct:
            key = f"domestic_cross:{coin}"
            if not is_alert_in_cooldown(state, key, now_jst, settings.alert_cooldown_hours):
                alerts.append(
                    {
                        "key": key,
                        "text": (
                            f"国内取引所間クロス **{coin}** {cross:+.2f}% "
                            f"({m.get('domestic_cross_pair') or '不明'})"
                        ),
                    }
                )

        apr = m.get("funding_apr_pct")
        if apr is not None and abs(apr) >= settings.funding_apr_alert_pct:
            key = f"funding_apr:{coin}"
            if not is_alert_in_cooldown(state, key, now_jst, settings.alert_cooldown_hours):
                alerts.append(
                    {
                        "key": key,
                        "text": f"FR年率 **{coin}** {apr:+.1f}%",
                    }
                )

    for token, basis in metrics["hl_basis"].items():
        b = basis.get("basis_pct")
        if b is not None and abs(b) >= settings.hl_basis_alert_pct:
            key = f"hl_basis:{token}"
            if not is_alert_in_cooldown(state, key, now_jst, settings.alert_cooldown_hours):
                alerts.append(
                    {
                        "key": key,
                        "text": f"HL現物-パープ ベーシス **{token}** {b:+.2f}%",
                    }
                )

    return alerts


def apply_cooldowns(alerts: list[dict[str, Any]], state: dict[str, Any], now_jst: datetime) -> None:
    """送信成功後に呼ぶ: 発火したアラートのクールダウンを開始する。"""
    for alert in alerts:
        mark_alert_fired(state, alert["key"], now_jst)


def format_alert_message(alerts: list[dict[str, Any]], run_at_jst: datetime) -> str:
    header = (
        f"📡 **spread-logger アラート** "
        f"{run_at_jst.strftime('%m/%d')}({WEEKDAYS_JA[run_at_jst.weekday()]}) "
        f"{run_at_jst.strftime('%H:%M')} JST"
    )
    lines = [header, ""]
    for alert in alerts:
        lines.append(f"・{alert['text']}")
    lines.append("")
    lines.append("※ 事実の報告のみ。売買判断は自分で行うこと。")
    return "\n".join(lines)


def format_error_message(error: str, run_at_jst: datetime) -> str:
    return (
        f"🚨 **spread-logger 実行エラー** {run_at_jst.strftime('%m/%d %H:%M')} JST\n"
        f"```\n{error[:500]}\n```"
    )
