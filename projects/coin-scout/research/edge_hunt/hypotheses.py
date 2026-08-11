"""エッジ候補の仮説定義。engine.py の実行系だけを使い、ここではシグナルの作り方だけを書く。

シグナルはすべて「足 t の終値までに確定している情報」だけで構成する。
FRは正時に確定するため、足 t の終値時点で使えるのは index<=t のFR → shift(1) をかけて保守側に寄せる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine import Panel, cross_sectional_weights


def _safe_funding(panel: Panel) -> pd.DataFrame:
    if panel.funding is None:
        raise RuntimeError("FRデータが無い")
    return panel.funding.reindex_like(panel.close).shift(1)


# --- H1: FRキャリー(横断・ドルニュートラル) ---------------------------------
# 仮説: 資金調達率が最も負の銘柄をロング / 最も正の銘柄をショートすると、
#       FR受取が価格ドリフトを上回る。方向を当てにいかない「キャリー収穫」。
def h1_funding_carry(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int) -> pd.DataFrame:
    f = _safe_funding(panel).rolling(lookback, min_periods=lookback).mean()
    return cross_sectional_weights(-f, tradable & f.notna(), top_n=top_n)


# --- H2: FR順張り(横断) -----------------------------------------------------
# 仮説: [[funding-extreme-strategy-rejected]] で「極端FRは反転でなく継続」と分かった。
#       ならFRが高い(ロング混雑)銘柄をロングする順張り版に価格ドリフトのエッジがあるか。
def h2_funding_momentum(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int) -> pd.DataFrame:
    f = _safe_funding(panel).rolling(lookback, min_periods=lookback).mean()
    return cross_sectional_weights(f, tradable & f.notna(), top_n=top_n)


# --- H3: 短期リバーサル(横断) -----------------------------------------------
# 仮説: 薄いアルトは短期の一方向フローで行き過ぎ、数時間で戻る。
#       時間帯(棄却済)でも清算ウィック(棄却済)でもない、純粋な横断リバーサル。
def h3_short_reversal(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int) -> pd.DataFrame:
    ret = panel.close / panel.close.shift(lookback) - 1.0
    return cross_sectional_weights(-ret, tradable & ret.notna(), top_n=top_n)


# --- H4: 横断モメンタム -------------------------------------------------------
# 仮説: 中期(1日〜1週間)ではトレンドが継続する。
def h4_momentum(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int) -> pd.DataFrame:
    ret = panel.close / panel.close.shift(lookback) - 1.0
    return cross_sectional_weights(ret, tradable & ret.notna(), top_n=top_n)


# --- H5: BTCリードラグ(横断) -------------------------------------------------
# 仮説: HLのアルト板は薄く、BTCの動きへの追随が遅れる。ベータ調整後に「まだ追いついていない」
#       銘柄をロング、「行き過ぎた」銘柄をショートすると、次の数時間で収束する。
def h5_btc_leadlag(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int, beta_window: int = 24 * 14) -> pd.DataFrame:
    if "BTC" not in panel.close.columns:
        raise RuntimeError("BTCが無い")
    r = np.log(panel.close).diff()
    rb = r["BTC"]
    cov = r.mul(rb, axis=0).rolling(beta_window, min_periods=beta_window // 2).mean()
    var = rb.pow(2).rolling(beta_window, min_periods=beta_window // 2).mean()
    beta = cov.div(var, axis=0).clip(-3, 3)

    move_b = rb.rolling(lookback, min_periods=lookback).sum()
    move_i = r.rolling(lookback, min_periods=lookback).sum()
    gap = beta.mul(move_b, axis=0) - move_i     # 正 = BTCに追いついていない(出遅れ)
    return cross_sectional_weights(gap, tradable & gap.notna(), top_n=top_n)


# --- H6: レンジ圧縮ブレイク(時系列・方向) -----------------------------------
# 仮説: ボラが縮んだあとのレンジ抜けは継続する(ボラのクラスタリング)。
#       横断中立ではなく方向を取るので、銘柄横断で均等配分したポートフォリオとして評価する。
def h6_squeeze_breakout(
    panel: Panel,
    tradable: pd.DataFrame,
    channel: int,
    hold: int,
    squeeze_pct: float = 0.4,
    vol_window: int = 24 * 7,
    gross_leverage: float = 1.0,
) -> pd.DataFrame:
    tr = (panel.high - panel.low) / panel.close
    atr = tr.rolling(24, min_periods=24).mean()
    atr_rank = atr.rolling(vol_window, min_periods=vol_window // 2).rank(pct=True)
    squeezed = atr_rank <= squeeze_pct

    prior_high = panel.high.shift(1).rolling(channel, min_periods=channel).max()
    prior_low = panel.low.shift(1).rolling(channel, min_periods=channel).min()
    long_sig = (panel.close > prior_high) & squeezed & tradable
    short_sig = (panel.close < prior_low) & squeezed & tradable

    raw = long_sig.astype(float) - short_sig.astype(float)
    # hold本ぶんポジションを維持(最新シグナルが上書き)
    held = raw.replace(0.0, np.nan).ffill(limit=hold - 1).fillna(0.0)
    held = held.where(tradable, 0.0)
    n_active = held.abs().sum(axis=1).replace(0, np.nan)
    return held.div(n_active, axis=0).fillna(0.0) * gross_leverage


# --- 対照群: ランダムシグナル -------------------------------------------------
# 基盤が「何もないところからプラスを作っていない」ことを確認するための対照。
def control_random(panel: Panel, tradable: pd.DataFrame, lookback: int, top_n: int, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    noise = pd.DataFrame(
        rng.standard_normal(panel.close.shape), index=panel.close.index, columns=panel.close.columns
    )
    smooth = noise.rolling(lookback, min_periods=lookback).mean()
    return cross_sectional_weights(smooth, tradable & smooth.notna(), top_n=top_n)
