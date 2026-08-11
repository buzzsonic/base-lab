"""パッシブ約定後のマークアウト(逆選択)を測る。H3を進めるか打ち切るかの判定材料。

問い: 最良気配に指値を置いて約定したとき、その直後に価格はどちらへ動くか。

指値で買えた = 誰かが売り叩いてきたということ。相手が情報を持っていれば価格は下がり続け、
半スプレッドを取ったつもりが負ける。これが逆選択で、メイカー戦略の生死を分ける。
[[hl-cross-sectional-reversal]] のメイカー前提の数字(test SR 3.5)は、
ここが十分小さいことを暗黙に仮定していた。その仮定を検証する。

**行列の位置で2通り出す**(実際は両者の間のどこか):
- front: 列の先頭。価格に触れた売り注文すべてで約定する。小口にも当たるので逆選択は軽い
- back : 列の最後尾。その価格の表示数量を食い尽くす売りが来て初めて約定する。
         大口の一撃で約定しやすく、こちらが現実に近い

使い方:
    python markout.py                       # 収集済み全ファイル
    python markout.py --coins KAITO,ONDO
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "maker_fills"
HORIZONS_MS = [1_000, 5_000, 30_000, 60_000, 300_000]
MAKER_FEE_BPS = 1.5   # HL標準メイカー手数料 0.015%(リベートではない)


def load(paths: list[str]) -> dict[str, dict[str, list]]:
    """coin -> {"bbo": [...], "trade": [...]} に読み分ける。

    収集中のファイルは gzip の終端マーカーがまだ無く、最後まで読むと EOFError になる。
    収集を止めずに途中経過を見たいので、読めたところまでを採用して打ち切る。
    プロセスを強制終了した場合も最終ファイルは同じ状態になるため、この処理は常に要る。
    """
    out: dict[str, dict[str, list]] = {}
    for path in sorted(paths):
        rows = 0
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # flush境界で行が切れることがある
                    coin = r.get("coin")
                    if not coin:
                        continue
                    bucket = out.setdefault(coin, {"bbo": [], "trade": []})
                    bucket["bbo" if r["t"] == "bbo" else "trade"].append(r)
                    rows += 1
        except EOFError:
            print(f"  ※ {Path(path).name} は収集中(または未終端)。{rows:,}行まで読んで継続")
    return out


def simulate(bbo: list[dict], trades: list[dict]) -> list[dict]:
    """BBOと約定を時系列に混ぜ、front/back それぞれのパッシブ約定を検出する。

    テイカーの売り(side="A")は、こちらの買い指値に当たる。買い(side="B")はその逆。
    """
    events = [(b["recv_ms"], 0, b) for b in bbo] + [(t["recv_ms"], 1, t) for t in trades]
    events.sort(key=lambda e: (e[0], e[1]))

    fills: list[dict] = []
    bid = ask = None
    bid_px = ask_px = None
    # 各サイドの「その価格が立ってから食われた累計数量」と「立った瞬間の表示数量」
    acc = {"bid": 0.0, "ask": 0.0}
    shown = {"bid": 0.0, "ask": 0.0}
    done_back = {"bid": False, "ask": False}

    for ts, kind, r in events:
        if kind == 0:
            if r["bid_px"] != bid_px:
                bid_px, acc["bid"], shown["bid"], done_back["bid"] = r["bid_px"], 0.0, r["bid_sz"], False
            if r["ask_px"] != ask_px:
                ask_px, acc["ask"], shown["ask"], done_back["ask"] = r["ask_px"], 0.0, r["ask_sz"], False
            bid, ask = r["bid_px"], r["ask_px"]
            continue

        if bid is None or ask is None or ask <= bid:
            continue
        mid = (bid + ask) / 2
        px, sz, side = r["px"], r["sz"], r.get("side")

        # テイカー売り → こちらの買い指値(bid)が約定しうる
        if side == "A" and px <= bid:
            fills.append({"ts": ts, "dir": 1, "px": bid, "mid": mid, "queue": "front"})
            acc["bid"] += sz
            if not done_back["bid"] and acc["bid"] >= shown["bid"] > 0:
                done_back["bid"] = True
                fills.append({"ts": ts, "dir": 1, "px": bid, "mid": mid, "queue": "back"})

        # テイカー買い → こちらの売り指値(ask)が約定しうる
        elif side == "B" and px >= ask:
            fills.append({"ts": ts, "dir": -1, "px": ask, "mid": mid, "queue": "front"})
            acc["ask"] += sz
            if not done_back["ask"] and acc["ask"] >= shown["ask"] > 0:
                done_back["ask"] = True
                fills.append({"ts": ts, "dir": -1, "px": ask, "mid": mid, "queue": "back"})

    return fills


def markouts(fills: list[dict], bbo: list[dict]) -> dict[tuple[str, int], np.ndarray]:
    """約定ごとに各ホライズンのマークアウト(bps)を出す。dir=+1が買い、-1が売り。

    重要: マークアウトには**半スプレッドが最初から乗っている**。
    買いは必ず mid より下(bid)で約定するので、価格が1ミリも動かなくても
    (mid - bid) ぶんプラスに出る。これはメイカーの取り分そのものなので損益としては正しいが、
    「価格が有利に動いた」と読み違えないよう、h=0 の半スプレッドも併せて出して分解する。
    ドリフト = markout(h) - 半スプレッド。逆選択があればドリフトはマイナスになる。
    """
    if not bbo or not fills:
        return {}
    times = np.array([b["recv_ms"] for b in bbo])
    mids = np.array([(b["bid_px"] + b["ask_px"]) / 2 for b in bbo])

    out: dict[tuple[str, int], list[float]] = {}
    for f in fills:
        # h=0 相当: 約定時点の mid と約定価格の差 = 取れた半スプレッド
        out.setdefault((f["queue"], 0), []).append(
            f["dir"] * (f["mid"] - f["px"]) / f["mid"] * 1e4
        )
        for h in HORIZONS_MS:
            idx = np.searchsorted(times, f["ts"] + h)
            if idx >= len(times):
                continue  # 収集末尾で先が無い
            future_mid = mids[idx]
            # 買いなら値上がりが利益、売りなら値下がりが利益
            bps = f["dir"] * (future_mid - f["px"]) / f["mid"] * 1e4
            out.setdefault((f["queue"], h), []).append(bps)
    return {k: np.array(v) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DATA_DIR)
    ap.add_argument("--coins", default="")
    args = ap.parse_args()

    paths = glob.glob(str(args.dir / "bbo_trades_*.ndjson.gz"))
    if not paths:
        print(f"データがありません: {args.dir}")
        return 1
    data = load(paths)
    wanted = {c.strip().upper() for c in args.coins.split(",") if c.strip()} or set(data)

    span_ms = 0
    all_mo: dict[tuple[str, int], list[float]] = {}
    per_coin: dict[str, dict[tuple[str, int], np.ndarray]] = {}
    print(f"{'銘柄':<9}{'BBO':>8}{'約定':>8}{'front約定':>10}{'back約定':>9}")
    for coin in sorted(data):
        if coin not in wanted:
            continue
        bbo, trades = data[coin]["bbo"], data[coin]["trade"]
        if not bbo:
            continue
        span_ms = max(span_ms, bbo[-1]["recv_ms"] - bbo[0]["recv_ms"])
        fills = simulate(bbo, trades)
        nf = sum(1 for f in fills if f["queue"] == "front")
        nb = sum(1 for f in fills if f["queue"] == "back")
        print(f"{coin:<9}{len(bbo):>8,}{len(trades):>8,}{nf:>10,}{nb:>9,}")
        mo = markouts(fills, bbo)
        per_coin[coin] = mo
        for key, arr in mo.items():
            all_mo.setdefault(key, []).extend(arr.tolist())

    print(f"\n収集時間: {span_ms/3600000:.2f}時間")
    if not all_mo:
        print("約定サンプルが足りません。収集を続けてください。")
        return 0

    print("\n" + "=" * 78)
    print("パッシブ約定後のマークアウト(bps、プラス=メイカー有利)")
    print("=" * 78)
    print(f"{'行列位置':<8}{'経過':>8}{'約定数':>9}{'平均':>9}{'半スプ':>8}{'ドリフト':>9}"
          f"{'手数料後':>10}{'標準誤差':>9}")
    for queue in ("front", "back"):
        half = np.array(all_mo.get((queue, 0), []))
        half_mean = half.mean() if half.size else float("nan")
        for h in HORIZONS_MS:
            arr = np.array(all_mo.get((queue, h), []))
            if arr.size == 0:
                continue
            se = arr.std(ddof=1) / np.sqrt(arr.size)
            print(f"{queue:<8}{f'{h//1000}秒':>8}{arr.size:>9,}{arr.mean():>9.2f}{half_mean:>8.2f}"
                  f"{arr.mean()-half_mean:>9.2f}{arr.mean()-MAKER_FEE_BPS:>10.2f}{se:>9.2f}")
        print()

    print("読み方:")
    print("  半スプ   = 約定した瞬間に取れている取り分(価格が動かなくても得られる)")
    print("  ドリフト = そこからの価格変化。**逆選択があればマイナス**になる")
    print("  手数料後 = マークアウト - メイカー手数料1.5bps。これがプラスでないと成立しない")
    print("  標準誤差の2倍を超える差でなければ、まだ何も言えない")

    # 1銘柄が全体を持ち上げていないかを確認する。KAITOのように出来高が突出した銘柄が
    # 混ざると、全体平均がその1銘柄の性質になってしまう。
    print("\n" + "=" * 78)
    print("銘柄別(back・60秒・手数料後bps) — 特定銘柄だけで持っていないかの確認")
    print("=" * 78)
    print(f"{'銘柄':<9}{'back約定':>9}{'手数料後':>10}{'標準誤差':>9}")
    for coin in sorted(per_coin):
        arr = per_coin[coin].get(("back", 60_000))
        if arr is None or arr.size < 2:
            continue
        se = arr.std(ddof=1) / np.sqrt(arr.size)
        print(f"{coin:<9}{arr.size:>9,}{arr.mean()-MAKER_FEE_BPS:>10.2f}{se:>9.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
