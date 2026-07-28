"""C-2 検証: 清算カスケード直後のウィック逆張り(flush reversion)エッジの自己完結バックテスト。

背景([[hl-cohort-fade-edge]] / [[funding-extreme-strategy-rejected]]):
- FR極値の逆張りは棄却済み(極端FRは反転でなく継続)。これはセンチメントの逆張り。
- 本検証が狙うのは別物 = 「強制清算(margin call)による非情報的なオーバーシュートの平均回帰」。
  清算はマージン維持できないアカウントの機械的な投げ売り/踏み上げで、
  情報を含まないため、投げが枯れると価格が戻りやすい、という**マイクロストラクチャ**仮説。

データ源は HL の candle_snapshot のみ(清算専用フィードが公開APIに無いため)。
清算カスケードを「大ウィック + 出来高スパイク + 終値回復」で代理検出する。

使い方(base-lab ルートから):
    PYTHONPATH=. <venv>/bin/python projects/coin-scout/research/flush_reversion_backtest.py

出力: フラッシュ検出後の順方向リターン分布を、無条件ベースラインと比較し、
手数料込みで期待値がプラスかを銘柄横断で表示する。
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.hyperliquid import HyperliquidApiError, HyperliquidClient

# ---- パラメータ(まず素直な既定値。あとで感度分析する) ----
INTERVAL = "5m"
INTERVAL_MS = 5 * 60 * 1000
LOOKBACK_DAYS = 30          # 取得する過去日数(5m×30日 ≈ 8640本 → ページング)
CANDLES_PER_REQ = 4000      # HLは5000上限。安全側で4000ずつ
ROLL_WINDOW = 48            # 出来高/レンジのローリング基準(48本=4時間)

# フラッシュ検出しきい値(ボラ相対にして銘柄横断で比較可能にする)
WICK_ATR_MULT = 1.5         # ヒゲが直近ATR(ローリング中央レンジ)の何倍以上か
WICK_MIN_PCT = 0.4          # かつ最低これだけの%ヒゲ(ノイズ床。メジャーの微小ヒゲ除外)
VOL_SPIKE_MULT = 2.5        # 出来高がローリング中央値の何倍以上か
CLOSE_RECOVER_FRAC = 0.5    # 終値がバー内レンジの上側(下側)何割に戻ったか

# 評価する保有期間(バー数)。5m×[1,3,6,12,24] = 5,15,30,60,120分
HORIZONS = [1, 3, 6, 12, 24]

# 手数料: エントリ=メイカー(0.015%) 相当、エグジット=テイカー(0.045%) の往復を保守的に。
# 実運用は指値主体だが、悲観側で両テイカー相当も併記する。
FEE_RT_OPTIMISTIC = 0.015 + 0.045   # %(片メイカー+片テイカー)
FEE_RT_PESSIMISTIC = 0.045 * 2      # %(両テイカー)

# 対象銘柄: 流動性のある主要 + カスケードが大きく出やすいボラ高アルト。
# OI上位から自動選定するが、最低限このコア群は含める。
CORE_COINS = ["BTC", "ETH", "SOL", "DOGE", "HYPE"]
EXTRA_TOP_N = 40            # OI上位から追加する銘柄数(サンプル数確保のため広めに)


@dataclass
class Candle:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float  # base volume


def parse_candles(raw: list[dict[str, Any]]) -> list[Candle]:
    out: list[Candle] = []
    for k in raw:
        try:
            out.append(
                Candle(
                    t=int(k["t"]),
                    o=float(k["o"]),
                    h=float(k["h"]),
                    l=float(k["l"]),
                    c=float(k["c"]),
                    v=float(k["v"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x.t)
    return out


def fetch_candles(client: HyperliquidClient, coin: str, days: int) -> list[Candle]:
    """ページングして candle_snapshot を days 日分集める。"""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = end_ms - days * 24 * 60 * 60 * 1000
    span = CANDLES_PER_REQ * INTERVAL_MS

    merged: dict[int, Candle] = {}
    cur = start_ms
    while cur < end_ms:
        chunk_end = min(cur + span, end_ms)
        try:
            raw = client.candle_snapshot(coin, INTERVAL, cur, chunk_end)
        except HyperliquidApiError:
            break
        for c in parse_candles(raw):
            merged[c.t] = c
        time.sleep(0.15)
        cur = chunk_end
    return [merged[t] for t in sorted(merged)]


def rolling_median(vals: list[float], i: int, window: int) -> float | None:
    lo = max(0, i - window)
    seg = vals[lo:i]
    if len(seg) < window // 2:
        return None
    return statistics.median(seg)


@dataclass
class Sample:
    coin: str
    direction: str            # "down"(下ヒゲ=ロング入) / "up"(上ヒゲ=ショート入)
    fwd: dict[int, float]     # close入り: horizon(bars)->順方向リターン(%), direction織込済
    fwd_wick: dict[int, float]  # 安値/高値入り(ベストケース指値約定)の順方向リターン(%)


def detect_and_measure(coin: str, candles: list[Candle]) -> tuple[list[Sample], list[dict[int, float]]]:
    """フラッシュ検出サンプルと、無条件ベースライン(全バー起点の順方向|リターン|)を返す。"""
    vols = [c.v for c in candles]
    ranges = [c.h - c.l for c in candles]
    samples: list[Sample] = []
    baseline: list[dict[int, float]] = []

    n = len(candles)
    max_h = max(HORIZONS)
    for i in range(ROLL_WINDOW, n - max_h):
        c = candles[i]
        med_v = rolling_median(vols, i, ROLL_WINDOW)
        atr = rolling_median(ranges, i, ROLL_WINDOW)   # 直近の代表的バーレンジ(価格単位)
        if not med_v or med_v <= 0 or not atr or atr <= 0:
            continue

        rng = c.h - c.l
        if rng <= 0 or c.c <= 0:
            continue

        body_lo = min(c.o, c.c)
        body_hi = max(c.o, c.c)
        lower_wick = body_lo - c.l              # 価格単位
        upper_wick = c.h - body_hi
        lower_wick_pct = lower_wick / c.c * 100
        upper_wick_pct = upper_wick / c.c * 100
        close_pos = (c.c - c.l) / rng          # 0=安値側, 1=高値側
        vol_spike = c.v / med_v

        # ベースライン: 全バーの「その後 h 本の絶対リターン中央値」を測るため記録
        base_fwd: dict[int, float] = {}
        for h in HORIZONS:
            base_fwd[h] = (candles[i + h].c - c.c) / c.c * 100
        baseline.append(base_fwd)

        # down-flush(ロング崩し): 大きい下ヒゲ(ATR相対+%床) + 出来高スパイク + 終値が上側へ回復
        is_down = (
            lower_wick >= WICK_ATR_MULT * atr
            and lower_wick_pct >= WICK_MIN_PCT
            and vol_spike >= VOL_SPIKE_MULT
            and close_pos >= CLOSE_RECOVER_FRAC
        )
        # up-flush(ショート踏み上げ): 大きい上ヒゲ + 出来高スパイク + 終値が下側へ回復
        is_up = (
            upper_wick >= WICK_ATR_MULT * atr
            and upper_wick_pct >= WICK_MIN_PCT
            and vol_spike >= VOL_SPIKE_MULT
            and (1 - close_pos) >= CLOSE_RECOVER_FRAC
        )

        # エントリ価格の2モードを両方測る:
        #   close = バー終値で成行(反発後に飛び乗る = 実際の裁量トレード)
        #   wick  = バー安値/高値で指値約定(ベストケースの流動性提供)
        if is_down:
            fwd = {h: (candles[i + h].c - c.c) / c.c * 100 for h in HORIZONS}       # close入ロング
            fwd_w = {h: (candles[i + h].c - c.l) / c.l * 100 for h in HORIZONS}     # 安値入ロング
            samples.append(Sample(coin, "down", fwd, fwd_w))
        elif is_up:
            fwd = {h: (c.c - candles[i + h].c) / c.c * 100 for h in HORIZONS}       # close入ショート
            fwd_w = {h: (c.h - candles[i + h].c) / c.h * 100 for h in HORIZONS}     # 高値入ショート
            samples.append(Sample(coin, "up", fwd, fwd_w))

    return samples, baseline


def summarize(samples: list[Sample], baseline: list[dict[int, float]]) -> None:
    if not samples:
        print("  フラッシュ検出ゼロ。しきい値を緩めるか対象銘柄を増やす必要あり。")
        return

    print(f"  フラッシュ検出数: {len(samples)}  (down={sum(1 for s in samples if s.direction=='down')}, "
          f"up={sum(1 for s in samples if s.direction=='up')})")

    for mode, attr in (("A) 終値で成行(裁量トレード相当)", "fwd"),
                       ("B) 安値/高値で指値約定(ベストケースMM)", "fwd_wick")):
        print(f"\n  --- {mode} ---")
        print(f"  {'H(bars)':>8} {'mean%':>8} {'median%':>8} {'win%':>7} {'net_opt%':>9} {'net_pes%':>9} {'base|med|%':>11}")
        for h in HORIZONS:
            vals = [getattr(s, attr)[h] for s in samples]
            mean = statistics.mean(vals)
            median = statistics.median(vals)
            win = sum(1 for v in vals if v > 0) / len(vals) * 100
            net_opt = mean - FEE_RT_OPTIMISTIC
            net_pes = mean - FEE_RT_PESSIMISTIC
            base_absmed = statistics.median([abs(b[h]) for b in baseline]) if baseline else float("nan")
            print(f"  {h:>8} {mean:>8.3f} {median:>8.3f} {win:>6.1f}% {net_opt:>8.3f} {net_pes:>8.3f} {base_absmed:>10.3f}")


# ---- 決定的テスト: 先読み無しの指値ラダー ----
# 前バーまでの情報だけで close[i-1] ± K×ATR に指値を置き、bar i の高安が触れたら約定。
# フラッシュ判定も出来高も使わない = 反発したと分かってから買う先読みを完全排除。
# 刺さったまま落ち続ける逆選択も込みの、真の流動性提供の期待値。
LADDER_K = [1.5, 2.0, 3.0]


def ladder_measure(candles: list[Candle]) -> dict[float, list[dict[int, float]]]:
    ranges = [c.h - c.l for c in candles]
    out: dict[float, list[dict[int, float]]] = {k: [] for k in LADDER_K}
    n = len(candles)
    max_h = max(HORIZONS)
    for i in range(ROLL_WINDOW, n - max_h):
        atr = rolling_median(ranges, i, ROLL_WINDOW)
        ref = candles[i - 1].c  # 前バー終値(先読み無し)
        if not atr or atr <= 0 or ref <= 0:
            continue
        c = candles[i]
        for k in LADDER_K:
            bid = ref - k * atr
            ask = ref + k * atr
            if c.l <= bid:  # 下ラダー約定 → ロング(fill=bid)
                out[k].append({h: (candles[i + h].c - bid) / bid * 100 for h in HORIZONS})
            elif c.h >= ask:  # 上ラダー約定 → ショート(fill=ask)
                out[k].append({h: (ask - candles[i + h].c) / ask * 100 for h in HORIZONS})
    return out


def summarize_ladder(by_k: dict[float, list[dict[int, float]]]) -> None:
    for k in LADDER_K:
        rows = by_k[k]
        print(f"\n  --- 指値ラダー K={k}×ATR (先読み無し) n={len(rows)} ---")
        if not rows:
            print("   約定ゼロ")
            continue
        print(f"  {'H(bars)':>8} {'mean%':>8} {'median%':>8} {'win%':>7} {'net_opt%':>9} {'net_pes%':>9}")
        for h in HORIZONS:
            vals = [r[h] for r in rows]
            mean = statistics.mean(vals)
            median = statistics.median(vals)
            win = sum(1 for v in vals if v > 0) / len(vals) * 100
            print(f"  {h:>8} {mean:>8.3f} {median:>8.3f} {win:>6.1f}% "
                  f"{mean - FEE_RT_OPTIMISTIC:>8.3f} {mean - FEE_RT_PESSIMISTIC:>8.3f}")


def pick_universe(client: HyperliquidClient) -> list[str]:
    coins = list(CORE_COINS)
    try:
        meta, ctxs = client.meta_and_asset_ctxs()
        universe = meta.get("universe", [])
        rows = []
        for u, ctx in zip(universe, ctxs):
            name = u.get("name")
            try:
                oi = float(ctx.get("openInterest", 0)) * float(ctx.get("markPx", 0))
            except (TypeError, ValueError):
                oi = 0.0
            if name:
                rows.append((name, oi))
        rows.sort(key=lambda r: r[1], reverse=True)
        for name, _ in rows[:EXTRA_TOP_N]:
            if name not in coins:
                coins.append(name)
    except HyperliquidApiError as exc:
        print(f"universe取得失敗(コア群のみで継続): {exc}")
    return coins


def main() -> None:
    client = HyperliquidClient(request_sleep_seconds=0.05)
    coins = pick_universe(client)
    print(f"対象 {len(coins)}銘柄 / interval={INTERVAL} / 過去{LOOKBACK_DAYS}日")
    print(f"しきい値: wick>={WICK_MIN_PCT}% vol_spike>={VOL_SPIKE_MULT}x close_recover>={CLOSE_RECOVER_FRAC}")
    print(f"手数料往復: 楽観={FEE_RT_OPTIMISTIC:.3f}% 悲観={FEE_RT_PESSIMISTIC:.3f}%")
    print("=" * 78)

    all_samples: list[Sample] = []
    all_baseline: list[dict[int, float]] = []
    all_ladder: dict[float, list[dict[int, float]]] = {k: [] for k in LADDER_K}

    for coin in coins:
        candles = fetch_candles(client, coin, LOOKBACK_DAYS)
        if len(candles) < ROLL_WINDOW + max(HORIZONS) + 10:
            print(f"[{coin}] ローソク不足({len(candles)}本)。スキップ")
            continue
        samples, baseline = detect_and_measure(coin, candles)
        for k, rows in ladder_measure(candles).items():
            all_ladder[k].extend(rows)
        span_h = (candles[-1].t - candles[0].t) / 3_600_000
        print(f"[{coin}] {len(candles)}本({span_h:.0f}h) flush={len(samples)}")
        all_samples.extend(samples)
        all_baseline.extend(baseline)

    print("=" * 78)
    print("【全銘柄 集約: フラッシュ検出】")
    summarize(all_samples, all_baseline)
    print()
    print("=" * 78)
    print("【全銘柄 集約: 先読み無し指値ラダー(決定的テスト)】")
    summarize_ladder(all_ladder)
    print()
    print("読み方: net_opt/net_pes が明確にプラスかつ base|med| を上回れば、")
    print("        単なるボラ取りでなく『フラッシュ後の回帰』にエッジがある証拠。")
    print("        win% と mean の符号が割れる場合は分布が歪(裾で稼ぐ)ので要注意。")


if __name__ == "__main__":
    main()
