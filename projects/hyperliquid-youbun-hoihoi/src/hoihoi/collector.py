from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .api import PublicApi
from .discovery import normalize_wallet


WS_URL = "wss://api.hyperliquid.xyz/ws"
JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jst_time_band(value: datetime) -> str:
    hour = value.astimezone(JST).hour
    return "jst_00_05" if hour < 6 else "jst_06_11" if hour < 12 else "jst_12_17" if hour < 18 else "jst_18_23"


def select_markets(meta_ctx: list, cutoff: float, alt_count: int, small_alt_count: int,
                   rotation_key: str) -> dict[str, list[str]]:
    """Select outcome-blind market coverage with a stable per-window rotation."""
    if not isinstance(meta_ctx, list) or len(meta_ctx) < 2:
        raise ValueError("metaAndAssetCtxs response is incomplete")
    universe = (meta_ctx[0] or {}).get("universe") or []
    contexts = meta_ctx[1] or []
    volumes: dict[str, float] = {}
    for meta, context in zip(universe, contexts):
        try:
            if meta.get("isDelisted"):
                continue
            name = str(meta["name"])
            volume = float(context.get("dayNtlVlm") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        volumes[name] = volume

    majors = [coin for coin in ("BTC", "ETH") if coin in volumes]
    alts = [coin for coin, volume in volumes.items() if coin not in majors and volume >= cutoff]
    small = [coin for coin, volume in volumes.items() if coin not in majors and 0 < volume < cutoff]
    alts.sort(key=lambda coin: (-volumes[coin], coin))
    # Rotate the thin tail deterministically instead of repeatedly observing only its largest names.
    small.sort()
    band = rotation_key.rsplit("|", 1)[-1]
    band_index = {"jst_00_05": 0, "jst_06_11": 1, "jst_12_17": 2, "jst_18_23": 3}.get(band, 0)
    day_key = rotation_key.split("|", 1)[0]
    base = int(hashlib.sha256(day_key.encode()).hexdigest(), 16) if small else 0
    offset = (base + band_index * max(small_alt_count, 1)) % len(small) if small else 0
    rotated = small[offset:] + small[:offset]
    return {"major": majors, "alt": alts[:alt_count], "small_alt": rotated[:small_alt_count]}


class Coverage:
    def __init__(self, requested: dict[str, list[str]]):
        self.requested = requested
        self.messages = Counter()
        self.trades = Counter()
        self.wallets: set[str] = set()
        self.reconnects = 0
        self.malformed_messages = 0
        self.errors = Counter()

    def observe(self, message: dict) -> int | None:
        if message.get("channel") != "trades" or not isinstance(message.get("data"), list):
            return None
        source_times = []
        for trade in message["data"]:
            coin = str(trade.get("coin") or "unknown")
            self.trades[coin] += 1
            for raw_wallet in trade.get("users") or []:
                wallet = normalize_wallet(raw_wallet)
                if wallet:
                    self.wallets.add(wallet)
            try:
                source_times.append(int(trade["time"]))
            except (KeyError, TypeError, ValueError):
                pass
        for coin in {str(trade.get("coin") or "unknown") for trade in message["data"]}:
            self.messages[coin] += 1
        return max(source_times) if source_times else None

    def summary(self) -> dict:
        requested_coins = [coin for coins in self.requested.values() for coin in coins]
        received = {coin for coin, count in self.trades.items() if count > 0}
        group_coverage = {}
        for group, coins in self.requested.items():
            observed = sum(coin in received for coin in coins)
            group_coverage[group] = {
                "requested_markets": len(coins), "observed_markets": observed,
                "coverage_ratio": observed / len(coins) if coins else None,
            }
        return {
            "requested_markets": requested_coins,
            "observed_markets": sorted(received),
            "missing_markets": sorted(set(requested_coins) - received),
            "messages_by_market": dict(self.messages),
            "trades_by_market": dict(self.trades),
            "unique_wallets": len(self.wallets),
            "group_coverage": group_coverage,
            "reconnects": self.reconnects,
            "malformed_messages": self.malformed_messages,
            "errors": dict(self.errors),
        }


async def collect(url: str, markets: dict[str, list[str]], raw_path: Path, duration: int,
                  stale_seconds: int, reconnect_seconds: float) -> Coverage:
    import websockets

    coverage = Coverage(markets)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + duration
    connection = 0
    with raw_path.open("a") as raw:
        while time.monotonic() < deadline:
            try:
                async with websockets.connect(url, open_timeout=15, ping_interval=20,
                                              max_size=16 * 1024 * 1024, max_queue=1024) as socket:
                    connection += 1
                    if connection > 1:
                        coverage.reconnects += 1
                    for coin in [item for values in markets.values() for item in values]:
                        await socket.send(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": coin}}))
                    last_message = time.monotonic()
                    while time.monotonic() < deadline:
                        timeout = min(10, max(.01, deadline - time.monotonic()))
                        try:
                            wire = await asyncio.wait_for(socket.recv(), timeout)
                        except asyncio.TimeoutError:
                            await socket.send(json.dumps({"method": "ping"}))
                            if time.monotonic() - last_message > stale_seconds:
                                raise TimeoutError("public trades stream is stale")
                            continue
                        received_at = int(time.time() * 1000)
                        last_message = time.monotonic()
                        if isinstance(wire, bytes):
                            wire = wire.decode("utf-8")
                        try:
                            message = json.loads(wire)
                        except (TypeError, ValueError):
                            coverage.malformed_messages += 1
                            continue
                        source_time = coverage.observe(message)
                        if message.get("channel") == "trades":
                            raw.write(json.dumps({"schema_version": 1, "channel": "trades", "wire": wire,
                                                  "source_time": source_time, "received_at": received_at,
                                                  "connection": connection}, ensure_ascii=False) + "\n")
                            raw.flush()
            except OSError as exc:
                if getattr(exc, "errno", None) in (5, 13, 28, 30):
                    raise
                coverage.errors[type(exc).__name__] += 1
                await asyncio.sleep(min(reconnect_seconds, max(0, deadline - time.monotonic())))
            except Exception as exc:
                coverage.errors[type(exc).__name__] += 1
                await asyncio.sleep(min(reconnect_seconds, max(0, deadline - time.monotonic())))
    return coverage


def run(args: argparse.Namespace) -> dict:
    if args.duration is not None and args.duration <= 0:
        raise ValueError("duration must be positive")
    config = json.loads(args.config.read_text())
    collector_config = config["discovery_collector"]
    started = datetime.now(timezone.utc)
    band = jst_time_band(started)
    rotation_key = f"{started.astimezone(JST).date()}|{band}"
    api = PublicApi(args.output / "raw-cache", config["api"]["min_request_interval_seconds"], config["api"]["retries"])
    market_snapshot = api.market_contexts(True)
    markets = select_markets(market_snapshot, config["classification"]["small_alt_notional_cutoff"],
                             collector_config["alt_markets_per_run"], collector_config["small_alt_markets_per_run"],
                             rotation_key)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output / f"date={started.astimezone(JST).date()}" / f"window={band}" / f"run={run_id}"
    raw_path = run_dir / "public.jsonl"
    write_json(run_dir / "market_snapshot.json", market_snapshot)
    coverage = asyncio.run(collect(args.ws_url, markets, raw_path, args.duration or collector_config["duration_seconds"],
                                   collector_config["stale_feed_seconds"], collector_config["reconnect_delay_seconds"]))
    finished = datetime.now(timezone.utc)
    manifest = {"schema_version": 1, "status": "success", "started_at": started.isoformat(),
                "finished_at": finished.isoformat(), "jst_date": str(started.astimezone(JST).date()),
                "jst_time_band": band, "rotation_key": rotation_key, "markets": markets,
                "raw_path": str(raw_path.relative_to(args.output)), **coverage.summary()}
    if not manifest["observed_markets"]:
        manifest["status"] = "no_trades_observed"
    write_json(run_dir / "coverage.json", manifest)
    write_json(args.output / "latest.json", manifest)
    if manifest["status"] != "success":
        raise RuntimeError("No trades observed; coverage is not successful")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Hyperliquid public Trades discovery collector")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/discovery")
    parser.add_argument("--duration", type=int)
    parser.add_argument("--ws-url", default=WS_URL)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
