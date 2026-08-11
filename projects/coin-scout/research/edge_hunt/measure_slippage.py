"""実板(l2Book)から成行のスリッページを実測し、コストモデルの仮定を検証する。

バックテストの採否はコスト前提でひっくり返る。仮定のまま「棄却」「採用」を言わないために、
実際の板を叩いた場合の平均約定価格のズレ(bps)を銘柄・クリップサイズ別に測る。

使い方: PYTHONPATH=. python projects/coin-scout/research/edge_hunt/measure_slippage.py
"""

from __future__ import annotations

import json
from pathlib import Path

from shared.hyperliquid import HyperliquidClient

CLIPS_USD = [2_000, 5_000, 10_000, 25_000, 50_000]
OUT = Path(__file__).resolve().parent / "results" / "slippage_measured.json"


def sweep(levels: list[dict], mid: float, notional: float) -> float | None:
    """板を上から食っていったときの平均約定価格の、中値からの乖離(bps)。"""
    remaining = notional
    cost = 0.0
    filled = 0.0
    for level in levels:
        px = float(level["px"])
        size_usd = float(level["sz"]) * px
        take = min(remaining, size_usd)
        cost += take / px * px  # notional
        filled += take / px     # coins
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0 or filled <= 0:
        return None  # 板が薄すぎて約定しきらない
    avg_px = notional / filled
    return abs(avg_px - mid) / mid * 1e4


def main() -> None:
    client = HyperliquidClient(request_sleep_seconds=0.15)
    meta, ctxs = client.meta_and_asset_ctxs()
    rows = []
    for asset, ctx in zip(meta["universe"], ctxs):
        if asset.get("isDelisted"):
            continue
        vol = float(ctx.get("dayNtlVlm") or 0)
        if vol < 300_000:
            continue
        rows.append((asset["name"], vol))
    rows.sort(key=lambda r: -r[1])
    print(f"日量$300k以上: {len(rows)}銘柄を実測")

    out = []
    for coin, vol in rows:
        book = client.post_info({"type": "l2Book", "coin": coin})
        levels = book.get("levels") or []
        if len(levels) != 2 or not levels[0] or not levels[1]:
            continue
        bid = float(levels[0][0]["px"])
        ask = float(levels[1][0]["px"])
        mid = (bid + ask) / 2
        rec = {
            "coin": coin,
            "day_vol_usd": vol,
            "half_spread_bps": (ask - bid) / 2 / mid * 1e4,
        }
        for clip in CLIPS_USD:
            rec[f"buy_{clip}"] = sweep(levels[1], mid, clip)
            rec[f"sell_{clip}"] = sweep(levels[0], mid, clip)
        out.append(rec)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))

    print(f"\n{'銘柄':<10}{'日量$M':>9}{'半スプ':>8}{'$5k':>9}{'$10k':>9}{'$25k':>9}")
    for r in out:
        def fmt(key: str) -> str:
            vals = [r.get(f"buy_{key}"), r.get(f"sell_{key}")]
            vals = [v for v in vals if v is not None]
            return f"{sum(vals)/len(vals):8.1f}" if vals else "     板薄"
        print(f"{r['coin']:<10}{r['day_vol_usd']/1e6:9.1f}{r['half_spread_bps']:8.1f}"
              f"{fmt('5000')}{fmt('10000')}{fmt('25000')}")

    # 出来高階層ごとの中央値 → engine.py の SLIPPAGE_TIERS の妥当性チェック
    print("\n出来高階層別の片道スリッページ中央値(bps, $10kクリップ):")
    tiers = [(50e6, "≥$50M"), (10e6, "≥$10M"), (3e6, "≥$3M"), (1e6, "≥$1M"), (0, "<$1M")]
    for i, (threshold, label) in enumerate(tiers):
        upper = tiers[i - 1][0] if i > 0 else float("inf")
        vals = []
        for r in out:
            if threshold <= r["day_vol_usd"] < upper:
                for side in ("buy", "sell"):
                    v = r.get(f"{side}_10000")
                    if v is not None:
                        vals.append(v)
        if vals:
            vals.sort()
            print(f"  {label:<8} n={len(vals)//2:3d}銘柄  中央値 {vals[len(vals)//2]:5.1f} bps  "
                  f"最悪 {vals[-1]:6.1f} bps")
        else:
            print(f"  {label:<8} 該当なし")


if __name__ == "__main__":
    main()
