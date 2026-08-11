"""グリッド検証を生き残った候補だけを深掘りする。

見るのは4点:
1. **減衰カーブ** — シグナルからhロ時間後までのコスト前リターン。真のエッジなら滑らかに立ち上がって
   減衰する。1本目だけ跳ねて即消えるならスプレッドのバウンス(執行不能)を拾っているだけ。
2. **流動性感度** — 対象を絞るとコストは下がるがエッジも痩せるはず。どちらが速いかで採否が決まる。
3. **期間安定性** — 月次で符号が安定しているか。1〜2か月の当たりで全体が持ち上がっていないか。
4. **損益分岐コスト曲線** — 片道コストをいくらに置くとゼロになるか。実測スリッページと突き合わせる。

使い方: python diagnose_survivors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (  # noqa: E402
    MAKER_BPS,
    TAKER_BPS,
    hold_weights,
    load_panel,
    run_backtest,
    split_masks,
    summarize,
    tradable_mask,
)
import hypotheses as H  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "results"


def decay_curve(panel, weights: pd.DataFrame, horizons=range(1, 49)) -> pd.Series:
    """ウェイト確定(足t終値)後、t+1始値から t+1+h 始値までの累積コスト前リターン。"""
    entry = panel.open.shift(-1)
    out = {}
    for h in horizons:
        exit_px = panel.open.shift(-(1 + h))
        r = (exit_px / entry - 1.0).replace([np.inf, -np.inf], np.nan)
        out[h] = (weights * r).sum(axis=1).replace(0.0, np.nan).mean() * 1e4
    return pd.Series(out, name="cum_bps")


def cost_curve(panel, weights: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """片道コスト(手数料+スリッページ)を固定値で振ったときのネットSharpe。"""
    rows = []
    for total_bps in [0, 1, 2, 3, 4, 5, 6, 8, 10, 15]:
        res = run_backtest(panel, weights, "cost", fee_bps=total_bps, slippage_mult=0.0)
        m = mask.reindex(res.net.index).fillna(False)
        s = summarize(res.slice(m), "test")
        rows.append({"片道コストbps": total_bps, "net_SR": round(s["sharpe_net"], 2),
                     "net年率%": round(s["ann_return_pct"], 1)})
    return pd.DataFrame(rows)


def main() -> None:
    panel = load_panel("1h", with_funding=True, min_bars=24 * 60)
    _, test_mask = split_masks(panel.close.index, train_frac=0.6, embargo=48)
    full_mask = pd.Series(True, index=panel.close.index)

    candidates = {
        "H3 リバーサル lb=12 top3": (H.h3_short_reversal, {"lookback": 12, "top_n": 3}),
        "H3 リバーサル lb=6 top5": (H.h3_short_reversal, {"lookback": 6, "top_n": 5}),
        "H5 リードラグ lb=12 top3": (H.h5_btc_leadlag, {"lookback": 12, "top_n": 3}),
    }

    print("=" * 100)
    print("1) 減衰カーブ(コスト前・累積bps / 全期間)")
    print("=" * 100)
    tradable = tradable_mask(panel, 1e6)
    curves = {}
    for label, (fn, params) in candidates.items():
        w = fn(panel, tradable, **params)
        curves[label] = decay_curve(panel, w)
    dc = pd.DataFrame(curves).round(2)
    print(dc.loc[[1, 2, 3, 6, 12, 24, 36, 48]].to_string())
    dc.to_csv(OUT_DIR / "decay_curves.csv")
    print("\n※ h=1 だけ大きく h=2 以降で伸びない場合、スプレッド往復に食われて執行不能と判断する。")

    print("\n" + "=" * 100)
    print("2) 流動性フィルタ感度(H3 lb=12 top3, hold=1, test期間)")
    print("=" * 100)
    rows = []
    for floor in [1e6, 3e6, 10e6, 30e6]:
        tr = tradable_mask(panel, floor)
        n_avg = tr.sum(axis=1).mean()
        if n_avg < 7:
            rows.append({"日量下限$M": floor / 1e6, "平均銘柄数": round(n_avg, 1), "備考": "銘柄不足"})
            continue
        w = H.h3_short_reversal(panel, tr, lookback=12, top_n=3)
        for tag, fee, sm in (("taker", TAKER_BPS, 1.0), ("half-maker", (TAKER_BPS + MAKER_BPS) / 2, 0.5)):
            res = run_backtest(panel, w, "liq", fee_bps=fee, slippage_mult=sm)
            s = summarize(res.slice(test_mask.reindex(res.net.index).fillna(False)), "test")
            rows.append({
                "日量下限$M": floor / 1e6, "平均銘柄数": round(n_avg, 1), "執行": tag,
                "gross_bps": round(s["gross_bps_per_bar"], 3),
                "cost_bps": round(s["cost_bps_per_bar"], 3),
                "net_SR": round(s["sharpe_net"], 2),
                "損益分岐bps": round(s["breakeven_cost_bps"], 2),
            })
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n" + "=" * 100)
    print("3) 月次のコスト前損益(bps/本) — 一部の月だけで持っていないか")
    print("=" * 100)
    monthly = {}
    for label, (fn, params) in candidates.items():
        w = fn(panel, tradable, **params)
        res = run_backtest(panel, w, label, fee_bps=0.0, slippage_mult=0.0)
        g = (res.gross + res.funding_pnl) * 1e4
        monthly[label] = g.groupby(g.index.to_period("M")).mean()
    print(pd.DataFrame(monthly).round(3).to_string())

    print("\n" + "=" * 100)
    print("4) 損益分岐コスト曲線(H3 lb=12 top3 hold=1, test期間)")
    print("=" * 100)
    w = H.h3_short_reversal(panel, tradable, lookback=12, top_n=3)
    print(cost_curve(panel, w, test_mask).to_string(index=False))

    print("\n" + "=" * 100)
    print("5) 保有本数(hold)を伸ばしたときの回転とネット(H3 lb=12 top3, test期間, taker)")
    print("=" * 100)
    rows = []
    for hold in [1, 2, 3, 6, 12, 24]:
        wh = hold_weights(w, hold)
        res = run_backtest(panel, wh, "hold", fee_bps=TAKER_BPS, slippage_mult=1.0)
        s = summarize(res.slice(test_mask.reindex(res.net.index).fillna(False)), "test")
        rows.append({"hold本": hold, "回転/本": round(s["turnover_per_bar"], 3),
                     "gross_bps": round(s["gross_bps_per_bar"], 3),
                     "cost_bps": round(s["cost_bps_per_bar"], 3),
                     "net_SR": round(s["sharpe_net"], 2),
                     "損益分岐bps": round(s["breakeven_cost_bps"], 2)})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
