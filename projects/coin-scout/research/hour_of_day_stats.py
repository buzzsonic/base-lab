"""草コインの「いつ歪むか」を時間帯・曜日で切り分ける。

狙い(非効率マップ F群): 戦略そのものではなく、**他の全戦略に掛けるフィルタ**を作る。
薄い時間帯ほど価格が壊れやすく、非効率が発生・持続しやすいという仮説を、
既存データ(HL 1時間足)だけで検証する。追加の収集は不要。

核心指標は「単位出来高あたりの値動き」= 価格インパクト代理。
出来高が少ないだけ、ボラが高いだけの時間帯ではなく、
**少ない売買で大きく動く=板が薄い**時間帯を特定する。

各コインを自分自身の平均で正規化してから合成するので、
値段もボラも桁違いなコインを混ぜても特定銘柄に引きずられない。

使い方:
    python hour_of_day_stats.py --min-vlm 1e6 --max-vlm 30e6 --out out.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

HL_INFO = "https://api.hyperliquid.xyz/info"
JST = timezone(timedelta(hours=9))
MAX_BARS = 5000  # HL candleSnapshot の返却上限
CONTROLS = ["BTC", "ETH"]  # 草コイン固有の効果を分離するための対照群
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def post(payload: dict[str, Any], retries: int = 3) -> Any:
    for attempt in range(retries):
        try:
            r = requests.post(HL_INFO, json=payload, timeout=30)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def select_universe(min_vlm: float, max_vlm: float) -> tuple[list[str], dict[str, float]]:
    """24時間ドル建て出来高で草コイン帯を抽出する。対照群は帯に関係なく必ず含める。"""
    meta, ctxs = post({"type": "metaAndAssetCtxs"})
    vlm: dict[str, float] = {}
    picked: list[str] = []
    for asset, ctx in zip(meta["universe"], ctxs):
        if asset.get("isDelisted"):
            continue
        name = asset["name"]
        v = float(ctx.get("dayNtlVlm") or 0.0)
        vlm[name] = v
        if min_vlm <= v <= max_vlm:
            picked.append(name)
    picked.sort(key=lambda c: -vlm[c])
    return picked, vlm


def fetch_candles(coin: str, bars: int = MAX_BARS) -> list[dict[str, Any]]:
    end = int(time.time() * 1000)
    start = end - bars * 3600 * 1000
    data = post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": "1h", "startTime": start, "endTime": end},
    })
    return data or []


def bar_metrics(c: dict[str, Any]) -> dict[str, float] | None:
    """1本のローソクから、時間帯比較に使う素の量を出す。"""
    o, h, l, cl = float(c["o"]), float(c["h"]), float(c["l"]), float(c["c"])
    if o <= 0 or l <= 0:
        return None
    base_vlm = float(c.get("v") or 0.0)
    ntl = base_vlm * (o + cl) / 2.0  # ドル建て出来高
    ret = cl / o - 1.0
    rng = (h - l) / o  # 高値安値レンジ = そのバーで実際に走った幅
    body = abs(cl - o) / o
    return {
        "ret": ret,
        "abs_ret": abs(ret),
        "range": rng,
        "wick_frac": (rng - body) / rng if rng > 0 else 0.0,  # 行って戻った割合
        "ntl": ntl,
        "trades": float(c.get("n") or 0.0),
    }


def normalized_buckets(
    rows: list[tuple[int, dict[str, float]]], keys: list[str], n_buckets: int
) -> dict[str, list[float | None]]:
    """コインごとに自分の全体平均で割ってから、バケツ平均を返す(1.0=自分の平均)。"""
    overall = {k: statistics.fmean([m[k] for _, m in rows]) for k in keys}
    out: dict[str, list[float | None]] = {k: [] for k in keys}
    for b in range(n_buckets):
        vals = [m for bucket, m in rows if bucket == b]
        for k in keys:
            if not vals or overall[k] == 0:
                out[k].append(None)
            else:
                out[k].append(statistics.fmean([v[k] for v in vals]) / overall[k])
    return out


def analyze(coins: list[str], n_buckets: int, bucket_fn) -> dict[str, Any]:
    keys = ["abs_ret", "range", "ntl", "trades", "wick_frac"]
    per_coin: dict[str, dict[str, list[float | None]]] = {}
    raw_ret: dict[int, list[float]] = defaultdict(list)  # 正規化しない生リターン(方向性を見る)
    bars_used: dict[str, int] = {}

    for coin in coins:
        try:
            candles = fetch_candles(coin)
        except Exception as e:  # 1銘柄の失敗で全体を落とさない
            print(f"  ! {coin}: 取得失敗 ({e})")
            continue
        rows: list[tuple[int, dict[str, float]]] = []
        for c in candles:
            m = bar_metrics(c)
            if m is None:
                continue
            dt = datetime.fromtimestamp(c["t"] / 1000, tz=JST)
            b = bucket_fn(dt)
            rows.append((b, m))
            raw_ret[b].append(m["ret"])
        if len(rows) < n_buckets * 20:  # バケツあたり最低20本は欲しい
            print(f"  ! {coin}: 本数不足 ({len(rows)}本) スキップ")
            continue
        per_coin[coin] = normalized_buckets(rows, keys, n_buckets)
        bars_used[coin] = len(rows)
        time.sleep(0.15)

    agg: dict[str, list[float | None]] = {}
    for k in keys:
        agg[k] = []
        for b in range(n_buckets):
            vals = [pc[k][b] for pc in per_coin.values() if pc[k][b] is not None]
            agg[k].append(statistics.fmean(vals) if vals else None)

    # 価格インパクト代理: 単位出来高あたりの値幅。高い=薄くて壊れやすい
    agg["impact"] = [
        (agg["range"][b] / agg["ntl"][b]) if agg["range"][b] and agg["ntl"][b] else None
        for b in range(n_buckets)
    ]
    mean_ret = [statistics.fmean(raw_ret[b]) if raw_ret[b] else None for b in range(n_buckets)]
    return {
        "coins": sorted(per_coin.keys()),
        "bars_used": bars_used,
        "agg": agg,
        "mean_ret_bp": [r * 1e4 if r is not None else None for r in mean_ret],
        "n_obs": [len(raw_ret[b]) for b in range(n_buckets)],
    }


def render(title: str, labels: list[str], res: dict[str, Any]) -> str:
    a = res["agg"]
    lines = [f"\n### {title}  ({len(res['coins'])}銘柄)", ""]
    lines.append("| 区分 | 値幅 | 出来高 | 約定数 | ヒゲ率 | **価格インパクト** | 平均riturn(bp) | 本数 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for b, lab in enumerate(labels):
        def f(k: str, digits: int = 2) -> str:
            v = a[k][b]
            return f"{v:.{digits}f}" if v is not None else "-"
        r = res["mean_ret_bp"][b]
        lines.append(
            f"| {lab} | {f('range')} | {f('ntl')} | {f('trades')} | {f('wick_frac')} | "
            f"**{f('impact')}** | {r:+.1f} | {res['n_obs'][b]:,} |" if r is not None
            else f"| {lab} | {f('range')} | {f('ntl')} | {f('trades')} | {f('wick_frac')} | **{f('impact')}** | - | 0 |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-vlm", type=float, default=1e6)
    ap.add_argument("--max-vlm", type=float, default=30e6)
    ap.add_argument("--limit", type=int, default=20, help="対象銘柄数の上限")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    universe, vlm = select_universe(args.min_vlm, args.max_vlm)
    coins = universe[: args.limit]
    print(f"草コイン帯 ${args.min_vlm/1e6:.0f}M〜${args.max_vlm/1e6:.0f}M: {len(universe)}銘柄 → 上位{len(coins)}銘柄を使用")
    print("  " + ", ".join(f"{c}(${vlm[c]/1e6:.1f}M)" for c in coins))

    report: dict[str, Any] = {"generated_at": datetime.now(JST).isoformat(), "universe": coins}
    md: list[str] = []

    for label, group in (("草コイン", coins), ("対照群(BTC/ETH)", CONTROLS)):
        print(f"\n[{label}] 1時間足を取得中...")
        hod = analyze(group, 24, lambda dt: dt.hour)
        dow = analyze(group, 7, lambda dt: dt.weekday())
        report[label] = {"hour_of_day": hod, "day_of_week": dow}
        md.append(render(f"{label} / 時間帯 (JST)", [f"{h:02d}時" for h in range(24)], hod))
        md.append(render(f"{label} / 曜日 (JST)", WEEKDAY_JA, dow))

    out_md = "\n".join(md)
    print(out_md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(args.out.replace(".json", ".md"), "w", encoding="utf-8") as f:
            f.write(out_md)
        print(f"\n保存 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
