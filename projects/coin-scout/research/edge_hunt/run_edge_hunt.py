"""仮説群を同一条件で回し、train で設計 → test で採点する。

原則:
- パラメータ選択は **train 期間のネットSharpe** だけで行う。test は最後に1回だけ見る。
- 単一の best だけでなく **系列全体(グリッド全部)の test 中央値** も出す。
  1本だけ光っているのは過学習、系列全体が正なら本物、という読み方をするため。
- 試した設定数を数え、多重検定の割引を明示する。

使い方(base-lab ルートから):
    PYTHONPATH=. python projects/coin-scout/research/edge_hunt/run_edge_hunt.py
"""

from __future__ import annotations

import itertools
import json
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

MIN_VOL_24H = 1e6      # 各時点で日量$1M以上の銘柄のみ売買対象

# 執行モデル3種。左から順に「現実 → 頑張った場合 → 理論上限」。
# maker-only は指値が必ず約定する前提なので実現不可能な上限値。エッジの有無の切り分け用。
FEE_MODELS = [
    ("taker", TAKER_BPS, 1.0),
    ("half-maker", (TAKER_BPS + MAKER_BPS) / 2, 0.5),
    ("maker-only(理論上限)", MAKER_BPS, 0.0),
]

# リバランス間隔(本)。回転コストを下げられるかどうかがエッジの生死を分けるため必ず振る。
HOLD_BARS_1H = [1, 2, 3, 6, 12, 24]
HOLD_BARS_4H = [1, 2, 3, 6, 12]

GRIDS_1H = {
    "H1 FRキャリー(横断)": (H.h1_funding_carry, {"lookback": [1, 8, 24, 72], "top_n": [3, 5]}),
    "H2 FR順張り(横断)": (H.h2_funding_momentum, {"lookback": [1, 8, 24, 72], "top_n": [3, 5]}),
    "H3 短期リバーサル(横断)": (H.h3_short_reversal, {"lookback": [1, 3, 6, 12], "top_n": [3, 5]}),
    "H4 モメンタム(横断)": (H.h4_momentum, {"lookback": [24, 72, 168], "top_n": [3, 5]}),
    "H5 BTCリードラグ(横断)": (H.h5_btc_leadlag, {"lookback": [1, 3, 6, 12], "top_n": [3, 5]}),
    "H6 レンジ圧縮ブレイク(方向)": (H.h6_squeeze_breakout, {"channel": [24, 48, 96], "hold": [6, 12, 24]}),
    "対照 ランダム": (H.control_random, {"lookback": [6, 24], "top_n": [3, 5]}),
}

# 4h足は2024-04まで遡れる(1h足は208日)。価格ベースの仮説だけ、別の相場つきで追試する。
# FR履歴は220日ぶんしか無いので、4h検証のFR損益は前半が欠落する(その旨レポートに明記)。
GRIDS_4H = {
    "H3 短期リバーサル(横断)": (H.h3_short_reversal, {"lookback": [1, 2, 3, 6], "top_n": [3, 5]}),
    "H4 モメンタム(横断)": (H.h4_momentum, {"lookback": [6, 18, 42], "top_n": [3, 5]}),
    "H5 BTCリードラグ(横断)": (H.h5_btc_leadlag, {"lookback": [1, 2, 3], "top_n": [3, 5]}),
    "H6 レンジ圧縮ブレイク(方向)": (H.h6_squeeze_breakout, {"channel": [6, 12, 24], "hold": [3, 6, 12]}),
    "対照 ランダム": (H.control_random, {"lookback": [2, 6], "top_n": [3, 5]}),
}


def grid_items(grid: dict) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, values)) for values in itertools.product(*(grid[k] for k in keys))]


def main() -> None:
    interval = sys.argv[1] if len(sys.argv) > 1 else "1h"
    grids = GRIDS_1H if interval == "1h" else GRIDS_4H
    min_bars = 24 * 60 if interval == "1h" else 6 * 60
    panel = load_panel(interval, with_funding=True, min_bars=min_bars)
    tradable = tradable_mask(panel, min_vol_usd_24h=MIN_VOL_24H,
                             min_history=(24 * 14 if interval == "1h" else 6 * 14))

    n_coins_avg = tradable.sum(axis=1).mean()
    print(f"パネル: {panel.close.shape[1]}銘柄 / {len(panel.close)}本 "
          f"({panel.close.index[0]:%Y-%m-%d} 〜 {panel.close.index[-1]:%Y-%m-%d})")
    print(f"FR取得済み: {0 if panel.funding is None else panel.funding.shape[1]}銘柄")
    print(f"各時点の売買対象(日量${MIN_VOL_24H/1e6:.0f}M以上): 平均{n_coins_avg:.1f}銘柄\n")

    train_mask, test_mask = split_masks(panel.close.index, train_frac=0.6, embargo=48)
    print(f"train {train_mask.sum()}本 / test {test_mask.sum()}本 (48本エンバーゴ)\n")

    hold_grid = HOLD_BARS_1H if interval == "1h" else HOLD_BARS_4H
    rows: list[dict] = []
    n_configs = 0
    for name, (fn, grid) in grids.items():
        for params in grid_items(grid):
            try:
                raw_weights = fn(panel, tradable, **params)
            except Exception as exc:  # データ不足などは飛ばす
                print(f"  skip {name} {params}: {exc}")
                continue
            for hold in hold_grid:
                n_configs += 1
                weights = hold_weights(raw_weights, hold)
                label = f"{name} {params} hold={hold}"
                for fee_tag, fee, slip_mult in FEE_MODELS:
                    res = run_backtest(panel, weights, label, fee_bps=fee, slippage_mult=slip_mult)
                    splits = (("train", train_mask), ("test", test_mask),
                              ("full", pd.Series(True, index=res.net.index)))
                    for split_name, mask in splits:
                        m = mask.reindex(res.net.index).fillna(False)
                        if m.sum() < 200:
                            continue
                        s = summarize(res.slice(m), split_name)
                        s.update({"family": name, "fee_model": fee_tag, "hold": hold, **params})
                        rows.append(s)
        print(f"  done: {name}")

    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT_DIR / f"all_results_{interval}.csv", index=False)

    pd.set_option("display.width", 240, "display.max_columns", 40)
    summary_rows = []
    for fee_tag, _, _ in FEE_MODELS:
        base = df[df.fee_model == fee_tag]
        for name in grids:
            fam = base[base.family == name]
            tr = fam[(fam.split == "train") & fam.sharpe_net.notna()]
            if tr.empty:
                continue
            best = tr.loc[tr.sharpe_net.idxmax()]
            key = {k: best[k] for k in list(grids[name][1]) + ["hold"]}
            te = fam[(fam.split == "test") & np.logical_and.reduce([fam[k] == v for k, v in key.items()])]
            te = te.iloc[0] if len(te) else None
            fam_test = fam[fam.split == "test"]
            summary_rows.append({
                "仮説": name,
                "執行": fee_tag,
                "最良パラメータ": json.dumps({k: int(v) for k, v in key.items()}, ensure_ascii=False),
                "train_SR": round(best.sharpe_net, 2),
                "test_SR": round(te.sharpe_net, 2) if te is not None else np.nan,
                "test_年率%": round(te.ann_return_pct, 1) if te is not None else np.nan,
                "test_p値": round(te.p_value, 3) if te is not None else np.nan,
                "系列test_SR中央値": round(fam_test.sharpe_net.median(), 2),
                "系列test_SR>0率": round((fam_test.sharpe_net > 0).mean(), 2),
                "損益分岐bps": round(te.breakeven_cost_bps, 2) if te is not None else np.nan,
                "回転/本": round(te.turnover_per_bar, 3) if te is not None else np.nan,
            })
    summary = pd.DataFrame(summary_rows)
    for fee_tag, _, _ in FEE_MODELS:
        print("=" * 130)
        print(f"【train で最良 → test で採点】執行モデル = {fee_tag}")
        print("=" * 130)
        print(summary[summary.執行 == fee_tag].drop(columns=["執行"]).to_string(index=False))
        print()
    summary.to_csv(OUT_DIR / f"summary_{interval}.csv", index=False)

    print(f"\n試した設定数: {n_configs} (手数料モデル2種 × 分割3種を含めるとさらに増える)")
    print(f"多重検定の目安: Bonferroni で p < {0.05/max(n_configs,1):.4f} を満たさなければ有意とみなさない")

    # グロス(コスト前)も出して「コストで死んでいるのか、そもそも予測力が無いのか」を切り分ける
    print("\n" + "=" * 108)
    print("【切り分け: test期間のコスト前 vs コスト後】")
    print("=" * 108)
    taker_test = df[(df.fee_model == "taker") & (df.split == "test")]
    diag = taker_test.groupby("family").agg(
        gross_bps=("gross_bps_per_bar", "median"),
        cost_bps=("cost_bps_per_bar", "median"),
        net_bps=("net_bps_per_bar", "median"),
        breakeven_bps=("breakeven_cost_bps", "median"),
        gross_SR=("sharpe_gross", "median"),
    ).round(3)
    print(diag.to_string())
    diag.to_csv(OUT_DIR / f"cost_diagnosis_{interval}.csv")


if __name__ == "__main__":
    main()
