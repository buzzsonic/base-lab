"""エッジ検証の共通基盤。仮説ごとに書き直さず、ここだけを信頼できる状態に保つ。

設計の柱(過去の検証で踏んだ地雷への対処):
1. **先読みの排除** — シグナルは足 t の終値まで。建玉は t+1 の *始値* で建て、t+1+h の始値で閉じる。
   同一足の高値/安値には一切触れない([[flush-reversion-rejected]] の敗因が先読みだったため)。
2. **銘柄別コスト** — HLのアルトは板が薄い。テイカー4.5bps + 出来高階層別スリッページを片道コストに。
3. **時点整合のユニバース** — 「今の出来高上位」ではなく、各リバランス時点の過去24hの出来高で選ぶ。
4. **train/test分割 + エンバーゴ** — 前60%で設計、後40%は触らない。境界は48本の空白を置く。
5. **ブロックブートストラップ** — 時系列の自己相関を潰さないよう24本のブロックで再標本化する。
6. **損益分岐コスト** — 「回転あたり総益 vs 実コスト」。Sharpeが高くてもここが負ければ棄却。

生存者バイアスは除去できない(上場廃止銘柄のローソク足がAPIに残らない)。既知の上振れ要因として扱う。
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "edge_hunt"

# --- コストモデル -------------------------------------------------------------
TAKER_BPS = 4.5   # HL標準テイカー 0.045%
MAKER_BPS = 1.5   # HL標準メイカー 0.015%

# 直近24hのUSD出来高 → 片道スリッページ(bps)。$1万クリップ想定。
# measure_slippage.py で実板(2026-08-03)を叩いて実測した中央値と突き合わせ済み:
#   実測中央値  ≥$50M:0.3 / ≥$10M:3.1 / ≥$3M:3.4 / ≥$1M:4.8 / <$1M:7.8
# 実測より安全側(高め)に置く。$10M帯だけ当初の仮定2.0bpsが甘かったので実測に合わせて引き上げた。
SLIPPAGE_TIERS = [
    (50e6, 1.0),
    (10e6, 3.5),
    (3e6, 4.0),
    (1e6, 7.0),
    (0.0, 12.0),
]

BARS_PER_YEAR = {"1h": 24 * 365, "4h": 6 * 365}


def _slippage_bps(vol_usd_24h: pd.DataFrame) -> pd.DataFrame:
    # 出来高不明(NaN)は最悪階層に落とす。NaNを「安い」側に倒すと過大評価になるため。
    vol = vol_usd_24h.fillna(0.0)
    out = pd.DataFrame(SLIPPAGE_TIERS[-1][1], index=vol.index, columns=vol.columns)
    for threshold, bps in sorted(SLIPPAGE_TIERS, key=lambda x: x[0]):
        out = out.where(vol < threshold, bps)
    return out


# --- パネル -------------------------------------------------------------------
@dataclass
class Panel:
    interval: str
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    vol_usd: pd.DataFrame           # 足あたりのUSD出来高
    funding: pd.DataFrame | None = None   # 1時間あたりFR(小数)。longが正なら支払い
    meta: dict = field(default_factory=dict)

    @property
    def vol_usd_24h(self) -> pd.DataFrame:
        window = 24 if self.interval == "1h" else 6
        return self.vol_usd.rolling(window, min_periods=window).sum()

    @property
    def bars_per_year(self) -> int:
        return BARS_PER_YEAR[self.interval]


def _load_gz(name: str) -> dict:
    with gzip.open(DATA_DIR / f"{name}.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)


def load_panel(interval: str = "1h", with_funding: bool = True, min_bars: int = 24 * 60) -> Panel:
    raw = _load_gz(f"candles_{interval}")
    frames: dict[str, pd.DataFrame] = {}
    series = {k: {} for k in ("o", "h", "l", "c", "vusd")}
    for coin, rows in raw.items():
        if len(rows) < min_bars:
            continue
        arr = np.asarray(rows, dtype=float)
        idx = pd.to_datetime(arr[:, 0].astype("int64"), unit="ms", utc=True)
        series["o"][coin] = pd.Series(arr[:, 1], index=idx)
        series["h"][coin] = pd.Series(arr[:, 2], index=idx)
        series["l"][coin] = pd.Series(arr[:, 3], index=idx)
        series["c"][coin] = pd.Series(arr[:, 4], index=idx)
        series["vusd"][coin] = pd.Series(arr[:, 5] * arr[:, 4], index=idx)
    for key, mapping in series.items():
        frames[key] = pd.DataFrame(mapping).sort_index()

    common = frames["c"].index
    funding = None
    if with_funding:
        try:
            fraw = _load_gz("funding_1h")
        except FileNotFoundError:
            fraw = {}
        fmap = {}
        for coin, rows in fraw.items():
            if coin not in frames["c"].columns or not rows:
                continue
            arr = np.asarray(rows, dtype=float)
            idx = pd.to_datetime(arr[:, 0].astype("int64"), unit="ms", utc=True).floor("h")
            s = pd.Series(arr[:, 1], index=idx)
            fmap[coin] = s[~s.index.duplicated(keep="last")]
        if fmap:
            fdf = pd.DataFrame(fmap).sort_index()
            if interval == "4h":
                fdf = fdf.resample("4h").sum()
            funding = fdf.reindex(common)

    return Panel(
        interval=interval,
        open=frames["o"],
        high=frames["h"],
        low=frames["l"],
        close=frames["c"],
        vol_usd=frames["vusd"],
        funding=funding,
    )


# --- バックテスト -------------------------------------------------------------
@dataclass
class BacktestResult:
    name: str
    net: pd.Series           # 期間ごとのネット損益(資本比)
    gross: pd.Series
    cost: pd.Series
    funding_pnl: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame
    interval: str

    def slice(self, mask: pd.Series) -> "BacktestResult":
        return BacktestResult(
            self.name, self.net[mask], self.gross[mask], self.cost[mask],
            self.funding_pnl[mask], self.turnover[mask], self.weights[mask], self.interval,
        )


def hold_weights(weights: pd.DataFrame, every: int) -> pd.DataFrame:
    """every 本に1回だけリバランスし、間は建玉を維持する。回転コストを下げる唯一の正攻法。

    ウェイトを据え置くだけで価格変動によるドリフトは無視する(実務では建て直さない方が
    コストが安いので、据え置きの方がむしろ保守的でない。ここは近似と割り切る)。
    """
    if every <= 1:
        return weights
    mask = np.arange(len(weights)) % every == 0
    return weights.where(pd.Series(mask, index=weights.index), other=np.nan).ffill().fillna(0.0)


def run_backtest(
    panel: Panel,
    weights: pd.DataFrame,
    name: str,
    fee_bps: float = TAKER_BPS,
    slippage_mult: float = 1.0,
    include_funding: bool = True,
) -> BacktestResult:
    """weights: 足 t の *終値時点* で決めた目標ウェイト。執行は t+1 の始値。

    区間リターンは open[t+1] → open[t+2]。よって足 t のウェイトが受け取る価格リターンは
    r_exec = open.shift(-2)/open.shift(-1) - 1 を t にアラインしたもの。
    """
    w = weights.reindex_like(panel.close).fillna(0.0)

    nxt_open = panel.open.shift(-1)          # t+1 の始値(建玉価格)
    nxt2_open = panel.open.shift(-2)         # t+2 の始値(手仕舞い価格)
    r_exec = (nxt2_open / nxt_open - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    gross = (w * r_exec).sum(axis=1)

    # ファンディングは保有区間 [t+1, t+2) に発生した分。HLは毎正時に直前1時間分を課金するので
    # 課金タイムスタンプは t+2。longが正のFRを払う。
    if include_funding and panel.funding is not None:
        f = panel.funding.reindex_like(panel.close).fillna(0.0).shift(-2)
        funding_pnl = -(w * f).sum(axis=1)
    else:
        funding_pnl = pd.Series(0.0, index=panel.close.index)

    # 回転コスト: 前区間のウェイトからの変化分を、その時点の流動性階層で課金
    slip = _slippage_bps(panel.vol_usd_24h).reindex_like(panel.close).fillna(SLIPPAGE_TIERS[-1][1])
    side_cost = (fee_bps + slip * slippage_mult) / 1e4
    dw = (w - w.shift(1).fillna(0.0)).abs()
    cost = (dw * side_cost).sum(axis=1)
    turnover = dw.sum(axis=1)

    net = gross + funding_pnl - cost
    valid = panel.close.notna().any(axis=1) & r_exec.notna().any(axis=1)
    valid.iloc[-2:] = False  # 執行価格が無い末尾2本は捨てる
    return BacktestResult(
        name, net[valid], gross[valid], cost[valid],
        funding_pnl[valid], turnover[valid], w[valid], panel.interval,
    )


# --- 統計 ---------------------------------------------------------------------
def block_bootstrap_p(returns: np.ndarray, block: int = 24, iterations: int = 4000, seed: int = 7) -> float:
    """平均>0 の片側p値。ブロック再標本化で自己相関を保ったまま帰無分布を作る。"""
    r = returns[~np.isnan(returns)]
    n = len(r)
    if n < block * 4:
        return float("nan")
    rng = np.random.default_rng(seed)
    centered = r - r.mean()
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block, size=(iterations, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(iterations, -1)[:, :n]
    means = centered[idx].mean(axis=1)
    return float((means >= r.mean()).mean())


def summarize(result: BacktestResult, label: str = "") -> dict:
    net = result.net.to_numpy()
    gross = result.gross.to_numpy() + result.funding_pnl.to_numpy()
    turnover = result.turnover.to_numpy()
    ppy = BARS_PER_YEAR[result.interval]
    n = len(net)
    sd = net.std(ddof=1) if n > 1 else np.nan

    total_turnover = turnover.sum()
    gross_sum = np.nansum(gross)
    # 損益分岐コスト: 片道何bpsまでなら総益が残るか
    breakeven_bps = (gross_sum / total_turnover * 1e4) if total_turnover > 0 else np.nan

    return {
        "strategy": result.name,
        "split": label,
        "bars": n,
        "net_bps_per_bar": float(np.nanmean(net) * 1e4),
        "gross_bps_per_bar": float(np.nanmean(gross) * 1e4),
        "cost_bps_per_bar": float(np.nanmean(result.cost.to_numpy()) * 1e4),
        "sharpe_net": float(np.nanmean(net) / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan,
        "sharpe_gross": float(np.nanmean(gross) / np.nanstd(gross, ddof=1) * np.sqrt(ppy)) if n > 1 else np.nan,
        "ann_return_pct": float(np.nanmean(net) * ppy * 100),
        "max_dd_pct": float(_max_drawdown(net) * 100),
        "turnover_per_bar": float(np.nanmean(turnover)),
        "breakeven_cost_bps": float(breakeven_bps),
        "p_value": block_bootstrap_p(net),
    }


def _max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumsum(np.nan_to_num(returns))
    peak = np.maximum.accumulate(equity)
    return float((equity - peak).min())


def split_masks(index: pd.Index, train_frac: float = 0.6, embargo: int = 48) -> tuple[pd.Series, pd.Series]:
    n = len(index)
    cut = int(n * train_frac)
    train = pd.Series(False, index=index)
    test = pd.Series(False, index=index)
    train.iloc[:cut] = True
    test.iloc[cut + embargo:] = True
    return train, test


# --- ウェイト構築の部品 -------------------------------------------------------
def cross_sectional_weights(
    signal: pd.DataFrame,
    tradable: pd.DataFrame,
    top_n: int = 5,
    gross_leverage: float = 1.0,
) -> pd.DataFrame:
    """シグナル上位を買い、下位を売るドルニュートラルのウェイト。

    ランクではなく上位/下位N本の等ウェイトにするのは、薄い銘柄に微小ウェイトを撒いて
    コストだけ払う事態を避けるため。
    """
    sig = signal.where(tradable)
    ranks = sig.rank(axis=1, ascending=False)
    counts = sig.notna().sum(axis=1)
    n_side = np.minimum(top_n, (counts // 2).clip(upper=top_n)).replace(0, np.nan)

    longs = ranks.le(n_side, axis=0) & sig.notna()
    shorts = ranks.gt(counts - n_side, axis=0) & sig.notna()

    w = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    n_long = longs.sum(axis=1).replace(0, np.nan)
    n_short = shorts.sum(axis=1).replace(0, np.nan)
    w = w.add(longs.div(n_long, axis=0).fillna(0.0) * (gross_leverage / 2), fill_value=0.0)
    w = w.sub(shorts.div(n_short, axis=0).fillna(0.0) * (gross_leverage / 2), fill_value=0.0)
    return w[(counts >= 2 * top_n)].reindex(signal.index).fillna(0.0)


def tradable_mask(panel: Panel, min_vol_usd_24h: float = 1e6, min_history: int = 24 * 14) -> pd.DataFrame:
    """各時点で「その時点までの情報だけ」で判定した取引可能マスク。"""
    liquid = panel.vol_usd_24h >= min_vol_usd_24h
    has_history = panel.close.notna().rolling(min_history, min_periods=min_history).sum() >= min_history
    priced = panel.open.shift(-1).notna() & panel.open.shift(-2).notna()
    return liquid & has_history & priced
