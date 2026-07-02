from datetime import datetime

from shared.discord import send_discord_embeds

from .logger import JST
from .signals import Signal


STYLE = {
    "funding": {"color": 0xFFAA00, "emoji": "⚡", "label": "ファンディング率異常"},
    "volume_oi": {"color": 0x00AAFF, "emoji": "📊", "label": "出来高 / OI 急増"},
    "breakout": {"color": 0x00FF88, "emoji": "🚨", "label": "ブレイクアウト"},
}

DIRECTION_LABEL = {
    "long": "🟢 ロング候補",
    "short": "🔴 ショート候補",
    "neutral": "⚪ 中立",
}


def _format_value(signal: Signal) -> str:
    if signal.kind == "funding":
        return f"{signal.value * 100:.4f}%"
    if signal.kind == "volume_oi":
        return f"{signal.value * 100:.1f}%" if abs(signal.value) < 1 else f"{signal.value:.1f}x"
    return f"${signal.value:.2f}"


def _send_embed(embed: dict, *, webhook_url: str | None, dry_run: bool, label: str) -> bool:
    return send_discord_embeds([embed], webhook_url=webhook_url, dry_run=dry_run, label=label)


def send_signal(signal: Signal, *, coin: str, webhook_url: str | None, dry_run: bool = False) -> bool:
    now_jst = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
    style = STYLE.get(signal.kind, {"color": 0xFFFFFF, "emoji": "🔔", "label": signal.kind})
    embed = {
        "title": f"{style['emoji']} [{coin}] {style['label']}",
        "description": signal.message,
        "color": style["color"],
        "fields": [
            {"name": "方向性", "value": DIRECTION_LABEL.get(signal.direction, signal.direction), "inline": True},
            {"name": "現在価格", "value": f"${signal.price:.2f}", "inline": True},
            {"name": "検知値", "value": _format_value(signal), "inline": True},
        ],
        "footer": {"text": f"Hyperliquid Signal Bot • {now_jst}"},
    }

    return _send_embed(
        embed,
        webhook_url=webhook_url,
        dry_run=dry_run,
        label=f"{signal.kind} / {signal.direction}",
    )


def send_heartbeat(*, coin: str, price: float, webhook_url: str | None, dry_run: bool = False) -> bool:
    signal = Signal(
        kind="heartbeat",
        direction="neutral",
        message=f"💚 {coin} の監視を継続しています。",
        value=0.0,
        price=price,
    )
    return send_signal(signal, coin=coin, webhook_url=webhook_url, dry_run=dry_run)


def send_no_signal_status(
    *,
    coin: str,
    price: float,
    checked_at_jst: datetime,
    webhook_url: str | None,
    dry_run: bool = False,
) -> bool:
    checked_at = checked_at_jst.strftime("%Y/%m/%d %H:%M JST")
    embed = {
        "title": f"💚 [{coin}] Bot 稼働中",
        "description": "シグナルなし。監視は正常に動いています。",
        "color": 0x888888,
        "fields": [
            {"name": "状態", "value": "シグナルなし", "inline": True},
            {"name": "現在価格", "value": f"${price:.2f}", "inline": True},
            {"name": "確認時刻", "value": checked_at, "inline": True},
        ],
        "footer": {"text": f"Hyperliquid Signal Bot • {checked_at}"},
    }

    return _send_embed(embed, webhook_url=webhook_url, dry_run=dry_run, label="no_signal")
