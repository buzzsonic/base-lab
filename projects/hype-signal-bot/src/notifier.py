from datetime import datetime

import requests

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


def send_signal(signal: Signal, *, coin: str, webhook_url: str | None, dry_run: bool = False) -> None:
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

    if dry_run:
        print(f"[DRY_RUN] Discord通知予定: {signal.kind} / {signal.direction}")
        print(embed)
        return
    if not webhook_url:
        print("[WARN] DISCORD_WEBHOOK_URL が未設定です")
        return

    response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
    response.raise_for_status()
    print(f"[OK] Discord通知送信: {signal.kind} / {signal.direction}")


def send_heartbeat(*, coin: str, price: float, webhook_url: str | None, dry_run: bool = False) -> None:
    signal = Signal(
        kind="heartbeat",
        direction="neutral",
        message=f"💚 {coin} の監視を継続しています。",
        value=0.0,
        price=price,
    )
    send_signal(signal, coin=coin, webhook_url=webhook_url, dry_run=dry_run)
