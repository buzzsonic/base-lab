"""HLのBBOと約定をWebSocketで記録する読み取り専用コレクター。発注は一切しない。

目的([[hl-cross-sectional-reversal]]):
横断リバーサル(H3)はコスト前の予測力が本物だったが、損益分岐が片道3-8bpsで、
テイカー実費(4.5bps手数料+5-7bpsスリッページ)に届かなかった。
残る可能性は「指値で在庫を提供する」側に回ることだが、それは
**指値がどれだけ約定し、約定した瞬間にどれだけ不利方向へ動くか(逆選択)** 次第。
ここを測らずにメイカー前提のバックテスト結果を信じてはいけない。

このコレクターはその生データを貯める。解析は markout.py。

元はCodexがNodeで書いた hl_microstructure_collector.mjs(BBO中央値147ms・約定の買い手売り手を全件取得できることを検証済み)。
このMacにNodeが無いこと、解析側がすべてPythonであることからPythonへ移植した。

使い方:
    # 短時間の疎通確認
    python collect_bbo_trades.py --seconds 120 --coins KAITO,ONDO
    # 継続収集(Ctrl-Cで停止、1時間ごとにファイル分割)
    python collect_bbo_trades.py --seconds 0
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

WS_URL = "wss://api.hyperliquid.xyz/ws"

# H3のエッジが実在した出来高帯(日量$1-6M)から選ぶ。メジャーで測っても意味がない
# ——エッジが無い場所の逆選択を測ることになるため。
DEFAULT_COINS = "DOGE,TAO,UNI,PENGU,LINK,ONDO,AAVE,CRV,KAITO,ENA"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "maker_fills"


class Writer:
    """1時間ごとにgzip NDJSONを切り替えて書く。"""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.key = ""
        self.handle: gzip.GzipFile | None = None
        self.rows = 0

    def _ensure(self, ts_ms: int) -> None:
        key = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y%m%d%H")
        if key == self.key and self.handle is not None:
            return
        if self.handle is not None:
            self.handle.close()
        self.key = key
        self.handle = gzip.open(self.out_dir / f"bbo_trades_{key}Z.ndjson.gz", "at", encoding="utf-8")

    def write(self, record: dict) -> None:
        self._ensure(record["recv_ms"])
        assert self.handle is not None
        self.handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.rows += 1

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def run(coins: list[str], seconds: int, out_dir: Path) -> int:
    writer = Writer(out_dir)
    stop = asyncio.Event()
    started = now_ms()
    counts = {"bbo": 0, "trades": 0}
    reconnects = 0

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async def deadline() -> None:
        if seconds > 0:
            await asyncio.sleep(seconds)
            stop.set()

    deadline_task = asyncio.create_task(deadline())

    while not stop.is_set():
        try:
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20, max_queue=4096) as ws:
                for coin in coins:
                    for channel in ("bbo", "trades"):
                        await ws.send(json.dumps({
                            "method": "subscribe",
                            "subscription": {"type": channel, "coin": coin},
                        }))
                print(f"接続: {len(coins)}銘柄 × 2チャンネルを購読", file=sys.stderr)

                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        # 全銘柄が30秒無音は異常。張り直す
                        raise ConnectionError("30秒間メッセージなし")

                    recv = now_ms()
                    msg = json.loads(raw)
                    channel = msg.get("channel")

                    if channel == "bbo":
                        d = msg["data"]
                        bid, ask = (d.get("bbo") or [None, None])[:2]
                        if not bid or not ask:
                            continue
                        writer.write({
                            "t": "bbo", "recv_ms": recv, "ex_ms": d.get("time"), "coin": d.get("coin"),
                            "bid_px": float(bid["px"]), "bid_sz": float(bid["sz"]), "bid_n": bid.get("n"),
                            "ask_px": float(ask["px"]), "ask_sz": float(ask["sz"]), "ask_n": ask.get("n"),
                        })
                        counts["bbo"] += 1

                    elif channel == "trades":
                        for tr in msg.get("data") or []:
                            writer.write({
                                "t": "trade", "recv_ms": recv, "ex_ms": tr.get("time"), "coin": tr.get("coin"),
                                # side は「テイカー側」。B=買い上がり / A=売り叩き
                                "side": tr.get("side"), "px": float(tr["px"]), "sz": float(tr["sz"]),
                                "tid": tr.get("tid"),
                            })
                            counts["trades"] += 1

        except asyncio.CancelledError:
            break
        except Exception as exc:  # 切断・パース失敗は再接続で吸収する
            if stop.is_set():
                break
            reconnects += 1
            print(f"再接続 {reconnects}回目 ({type(exc).__name__}: {exc})", file=sys.stderr)
            await asyncio.sleep(min(2 * reconnects, 15))

    deadline_task.cancel()
    writer.close()
    elapsed = (now_ms() - started) / 1000
    print(f"\n収集終了: {elapsed:.0f}秒 / BBO {counts['bbo']:,}件 / 約定 {counts['trades']:,}件 "
          f"/ 再接続 {reconnects}回 → {out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default=DEFAULT_COINS)
    ap.add_argument("--seconds", type=int, default=0, help="0で無期限(シグナルまで)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    return asyncio.run(run(coins, args.seconds, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
