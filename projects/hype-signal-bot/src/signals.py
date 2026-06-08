import statistics
from dataclasses import dataclass
from typing import Any


FUNDING_LONG_THRESHOLD = 0.0005
FUNDING_SHORT_THRESHOLD = -0.0002
VOLUME_SPIKE_MULTIPLIER = 2.5
OI_SPIKE_PCT = 0.05
BREAKOUT_CANDLES = 20


@dataclass(frozen=True)
class Signal:
    kind: str
    direction: str
    message: str
    value: float
    price: float


def check_funding(ctx: dict[str, Any]) -> Signal | None:
    funding = float(ctx.get("funding", 0))
    price = float(ctx.get("markPx", 0))

    if funding >= FUNDING_LONG_THRESHOLD:
        return Signal(
            kind="funding",
            direction="short",
            message="🔴 ファンディング率が過熱しています。短期ショート候補です。",
            value=funding,
            price=price,
        )
    if funding <= FUNDING_SHORT_THRESHOLD:
        return Signal(
            kind="funding",
            direction="long",
            message="🟢 ファンディング率が売られすぎです。短期ロング候補です。",
            value=funding,
            price=price,
        )
    return None


def check_volume_oi(
    ctx: dict[str, Any],
    prev_oi: float | None,
    candles: list[dict[str, Any]],
) -> Signal | None:
    price = float(ctx.get("markPx", 0))
    oi = float(ctx.get("openInterest", 0))

    oi_change = 0.0
    oi_spike = False
    if prev_oi and prev_oi > 0:
        oi_change = (oi - prev_oi) / prev_oi
        oi_spike = abs(oi_change) >= OI_SPIKE_PCT

    volume_ratio = 0.0
    volume_spike = False
    if len(candles) >= 12:
        lookback = candles[:-1]
        latest = candles[-1]
        avg_volume = statistics.mean(float(c["v"]) for c in lookback if float(c["v"]) >= 0)
        latest_volume = float(latest["v"])
        if avg_volume > 0:
            volume_ratio = latest_volume / avg_volume
            volume_spike = volume_ratio >= VOLUME_SPIKE_MULTIPLIER

    if not oi_spike and not volume_spike:
        return None

    direction = "neutral"
    price_change = 0.0
    if len(candles) >= 2:
        prev_close = float(candles[-2]["c"])
        latest_close = float(candles[-1]["c"])
        if prev_close > 0:
            price_change = (latest_close - prev_close) / prev_close

    if oi_change > 0 and price_change > 0:
        direction = "long"
    elif oi_change > 0 and price_change < 0:
        direction = "short"

    parts = []
    if oi_spike:
        parts.append(f"OI変化 {oi_change * 100:.1f}%")
    if volume_spike:
        parts.append(f"5分足出来高 {volume_ratio:.1f}倍")

    return Signal(
        kind="volume_oi",
        direction=direction,
        message="📊 " + " / ".join(parts) + "。出来高と建玉の急変を検知しました。",
        value=oi_change if oi_spike else volume_ratio,
        price=price,
    )


def check_breakout(candles: list[dict[str, Any]]) -> Signal | None:
    if len(candles) < BREAKOUT_CANDLES + 1:
        return None

    lookback = candles[-(BREAKOUT_CANDLES + 1) : -1]
    highs = [float(c["h"]) for c in lookback]
    lows = [float(c["l"]) for c in lookback]
    resistance = max(highs)
    support = min(lows)

    latest = candles[-1]
    close = float(latest["c"])
    volume = float(latest["v"])
    avg_volume = statistics.mean(float(c["v"]) for c in lookback)
    volume_confirmed = volume >= avg_volume * 1.5

    if close > resistance and volume_confirmed:
        return Signal(
            kind="breakout",
            direction="long",
            message=f"🚀 上方ブレイクアウト。レジスタンス ${resistance:.2f} を突破しました。",
            value=resistance,
            price=close,
        )
    if close < support and volume_confirmed:
        return Signal(
            kind="breakout",
            direction="short",
            message=f"💥 下方ブレイクダウン。サポート ${support:.2f} を割りました。",
            value=support,
            price=close,
        )
    return None
