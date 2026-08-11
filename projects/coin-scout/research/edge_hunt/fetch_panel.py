"""HLの公開APIからバックテスト用パネルを取得してローカルにキャッシュする。

APIの制約(2026-08-03 実測):
- candleSnapshot は startTime を古くしても「直近5000本」しか返らない(過去へのページング不可)。
    1h  → 約208日 (2026-01-07〜)
    4h  → 約833日 (2024-04-22〜)
    15m → 約52日
- fundingHistory は1回500件。startTime を進めながら前方ページングできる。
- isDelisted の銘柄はローソク足が空 → **生存者バイアスは除去不能**。レポートで明示する。

出力: projects/coin-scout/data/edge_hunt/*.json.gz (gitignore対象)

使い方(base-lab ルートから):
    PYTHONPATH=. python projects/coin-scout/research/edge_hunt/fetch_panel.py
"""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from shared.hyperliquid import HyperliquidApiError, HyperliquidClient

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "edge_hunt"
CANDLES_LIMIT = 5000

# FR履歴は1銘柄10コール前後かかるので、最低流動性を満たす銘柄に絞る。
# (今日の出来高ではなく期間中央値で絞ることで「今流行りの銘柄」への偏りを抑える)
FUNDING_MIN_MEDIAN_HOURLY_USD = 20_000
MIN_1H_BARS = 24 * 90


def write_gz(name: str, payload: object) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def fetch_universe(client: HyperliquidClient) -> list[dict]:
    meta, ctxs = client.meta_and_asset_ctxs()
    universe = []
    for asset, ctx in zip(meta["universe"], ctxs):
        universe.append(
            {
                "name": asset["name"],
                "max_leverage": asset.get("maxLeverage"),
                "only_isolated": bool(asset.get("onlyIsolated")),
                "is_delisted": bool(asset.get("isDelisted")),
                "sz_decimals": asset.get("szDecimals"),
                "day_ntl_vlm": float(ctx.get("dayNtlVlm") or 0.0),
                "open_interest": float(ctx.get("openInterest") or 0.0),
                "mark_px": float(ctx.get("markPx") or 0.0),
            }
        )
    return universe


def fetch_candles(client: HyperliquidClient, coins: list[str], interval: str, days: int) -> dict[str, list]:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days * 86_400_000
    out: dict[str, list] = {}
    for index, coin in enumerate(coins, start=1):
        try:
            rows = client.candle_snapshot(coin, interval, start_ms, now_ms)
        except HyperliquidApiError as exc:
            print(f"  !! {coin} {interval}: {exc}")
            continue
        # [t_open, open, high, low, close, volume(coin), trades] の最小形に落とす
        out[coin] = [
            [int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), float(r["v"]), int(r.get("n") or 0)]
            for r in rows
        ]
        if index % 25 == 0:
            print(f"  {interval}: {index}/{len(coins)} 銘柄")
    return out


def fetch_funding(client: HyperliquidClient, coins: list[str], days: int) -> dict[str, list]:
    now_ms = int(time.time() * 1000)
    out: dict[str, list] = {}
    for index, coin in enumerate(coins, start=1):
        cursor = now_ms - days * 86_400_000
        rows: list[list] = []
        seen: set[int] = set()
        while cursor < now_ms:
            try:
                page = client.funding_history(coin, cursor, now_ms)
            except HyperliquidApiError as exc:
                print(f"  !! funding {coin}: {exc}")
                break
            if not page:
                break
            fresh = 0
            for r in page:
                ts = int(r["time"])
                if ts in seen:
                    continue
                seen.add(ts)
                rows.append([ts, float(r["fundingRate"]), float(r.get("premium") or 0.0)])
                fresh += 1
            last_ts = max(int(r["time"]) for r in page)
            if fresh == 0 or last_ts <= cursor:
                break
            cursor = last_ts + 1
        rows.sort()
        out[coin] = rows
        print(f"  funding {index}/{len(coins)} {coin}: {len(rows)}件")
    return out


def main() -> None:
    client = HyperliquidClient(request_sleep_seconds=0.12, retries=5)

    print("1) universe")
    universe = fetch_universe(client)
    live = [u["name"] for u in universe if not u["is_delisted"]]
    delisted = [u["name"] for u in universe if u["is_delisted"]]
    print(f"   稼働 {len(live)} / 上場廃止 {len(delisted)}")
    write_gz("universe", universe)

    print("2) 1h candles (約208日)")
    c1h = fetch_candles(client, live, "1h", 220)
    write_gz("candles_1h", c1h)

    print("3) 4h candles (約833日)")
    c4h = fetch_candles(client, live, "4h", 900)
    write_gz("candles_4h", c4h)

    # FR取得対象を1h足の実績流動性で選別
    def median(values: list[float]) -> float:
        s = sorted(values)
        return s[len(s) // 2] if s else 0.0

    funding_coins = []
    for coin, rows in c1h.items():
        if len(rows) < MIN_1H_BARS:
            continue
        vol_usd = [r[5] * r[4] for r in rows]
        if median(vol_usd) >= FUNDING_MIN_MEDIAN_HOURLY_USD:
            funding_coins.append(coin)
    funding_coins.sort()
    print(f"4) funding history: {len(funding_coins)} 銘柄")
    fund = fetch_funding(client, funding_coins, 220)
    write_gz("funding_1h", fund)

    print("完了:", OUT_DIR)


if __name__ == "__main__":
    main()
