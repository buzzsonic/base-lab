from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow as pa

from .api import PublicApi
from .classify import classify_wallet
from .discovery import leaderboard_candidates, merge_sources, trade_stream_candidates
from .storage import write_csv, write_json, write_parquet


JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLIC_STREAMS = [
    Path.home() / "Documents/Codex/2026-09-09/new-chat/outputs/actor-event-db/data/live-final/public.jsonl",
    Path.home() / "Documents/Codex/2026-09-09/new-chat/outputs/actor-event-db/data/hype-ten-minute-20260917/public.jsonl",
    Path.home() / "Documents/Codex/2026-09-09/new-chat/outputs/actor-event-db/data/cashcat-ten-minute-20260917/public.jsonl",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def quality_summary(rows: list[dict]) -> dict:
    count = len(rows)
    source_counts = Counter(r["discovery_source"] for r in rows)
    return {
        "wallets": count,
        "duplicates": count - len({r["wallet"] for r in rows}),
        "inactive": sum(r["status"] == "INACTIVE" for r in rows),
        "bot_suspected": sum(bool(r["bot_suspected"]) for r in rows),
        "mm_suspected": sum(bool(r["mm_suspected"]) for r in rows),
        "arbitrage_suspected": sum(bool(r["arbitrage_suspected"]) for r in rows),
        "farm_suspected": sum(bool(r["farm_suspected"]) for r in rows),
        "capped_fill_histories": sum(not bool(r["data_complete"]) for r in rows),
        "large_share": sum(r["size_class"] == "large" for r in rows) / count if count else 0,
        "leaderboard_only_share": source_counts.get("official_leaderboard", 0) / count if count else 0,
        "sources": dict(source_counts),
        "frequency_bands": dict(Counter(r["frequency_class"] for r in rows)),
        "size_bands": dict(Counter(r["size_class"] for r in rows)),
        "symbol_profiles": dict(Counter(r["symbol_profile"] for r in rows)),
        "activity_time_bands": dict(Counter(r["activity_time_band"] for r in rows)),
        "active_days_bands": dict(Counter(r["active_days_band"] for r in rows)),
        "leaderboard_rank_bands": dict(Counter(r["leaderboard_rank_band"] for r in rows)),
    }


STRATA = ("frequency_class", "size_class", "symbol_profile", "activity_time_band",
          "active_days_band", "leaderboard_rank_band", "discovery_source")


def stratified_select(rows: list[dict], target: int) -> list[dict]:
    """Greedily cover underrepresented marginal strata; deterministic and outcome-blind."""
    remaining = list(rows)
    selected: list[dict] = []
    counts = {field: Counter() for field in STRATA}
    while remaining and len(selected) < target:
        def score(row: dict) -> tuple[float, str]:
            coverage = sum(1.0 / (1 + counts[field][str(row.get(field, "unknown"))]) for field in STRATA)
            quality = .20 if row["status"] != "INACTIVE" else 0
            cap_penalty = .10 if not row["data_complete"] else 0
            stable = hashlib.sha256(row["wallet"].encode()).hexdigest()
            return coverage + quality - cap_penalty, stable
        best = max(remaining, key=score)
        remaining.remove(best)
        best["poc_selected"] = True
        selected.append(best)
        for field in STRATA:
            counts[field][str(best.get(field, "unknown"))] += 1
    for row in remaining:
        row["poc_selected"] = False
    return selected


def small_alt_universe(meta_ctx: list, cutoff: float) -> set[str]:
    if not isinstance(meta_ctx, list) or len(meta_ctx) < 2:
        return set()
    universe = (meta_ctx[0] or {}).get("universe", [])
    contexts = meta_ctx[1] or []
    result = set()
    for meta, ctx in zip(universe, contexts):
        try:
            if float(ctx.get("dayNtlVlm") or 0) < cutoff and meta.get("name") not in {"BTC", "ETH"}:
                result.add(str(meta["name"]))
        except (TypeError, ValueError, KeyError):
            continue
    return result


def post_discord(message: str) -> str:
    url = os.environ.get("YOUBUN_HOIHOI_DISCORD_WEBHOOK_URL")
    if not url:
        return "SKIPPED: secret not configured"
    request = Request(url, data=json.dumps({"content": message}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=30) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Discord HTTP {response.status}")
    return "SENT"


def run_poc(args: argparse.Namespace) -> dict:
    config = load_config(args.config)
    now = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    out = args.output
    api = PublicApi(out / "raw-cache", config["api"]["min_request_interval_seconds"], config["api"]["retries"])
    target = args.limit or config["sampling"]["poc_wallets"]
    pool_target = max(target, target * int(config["sampling"].get("pool_multiplier", 2)))
    event_target = pool_target // 2
    streams = args.public_stream or DEFAULT_PUBLIC_STREAMS
    event_rows = trade_stream_candidates(streams, event_target)
    leaderboard_rows = leaderboard_candidates(api.leaderboard(args.refresh), pool_target)
    candidates = merge_sources([event_rows, leaderboard_rows], pool_target)
    small_alts = small_alt_universe(api.market_contexts(args.refresh), config["classification"]["small_alt_notional_cutoff"])
    pool = []
    for index, source in enumerate(candidates, 1):
        wallet = source["wallet"]
        fills = api.user_fills(wallet, args.refresh)
        perp_state = api.clearinghouse_state(wallet, args.refresh)
        spot_state = api.spot_state(wallet, args.refresh)
        row = classify_wallet(wallet, fills, perp_state, spot_state, now, source, config, small_alts)
        row["eligible_after"] = (now + timedelta(days=config["observation_days"])).isoformat()
        pool.append(row)
        print(f"[{index}/{len(candidates)}] {wallet} perp30d={row['perp_trade_count_30d']} status={row['status']}", file=sys.stderr)
    registry = stratified_select(pool, target)
    # First-seen candidates cannot be promoted in the same run. Future weekly runs merge history before promotion.
    sample = [r for r in registry if r["status"] == "ACTIVE"]
    version = f"sample_{now.astimezone(JST).strftime('%Y%m%d')}"
    for row in sample:
        row["sample_version"] = version
        row["sample_created_at"] = now.isoformat()
    arbitrage = [r for r in registry if r["arbitrage_suspected"] or r["funding_arbitrage_suspected"]]
    write_parquet(out / "wallet_registry.parquet", registry)
    write_parquet(out / "discovery_pool.parquet", pool)
    write_parquet(out / "research_sample.parquet", sample, [("wallet", pa.string()), ("sample_version", pa.string()),
                                                               ("sample_created_at", pa.string())])
    write_csv(out / "arbitrage_wallets.csv", arbitrage,
              ["wallet", "first_seen", "arbitrage_suspected", "funding_arbitrage_suspected", "suspicion_reason"])
    md = ["# Arbitrage / funding-neutral suspicion review", "",
          "> Heuristic candidates only. Do not treat these labels as confirmed strategies.", "",
          "| wallet | detected_at | suspected_type | reason |", "|---|---|---|---|"]
    for row in arbitrage:
        md.append(f"| `{row['wallet']}` | {row['first_seen']} | funding/arbitrage | {row['suspicion_reason']} |")
    if not arbitrage:
        md.append("| - | - | none observed in this PoC | - |")
    (out / "ARBITRAGE_WALLETS.md").write_text("\n".join(md) + "\n")
    quality = quality_summary(registry)
    pool_quality = quality_summary(pool)
    manifest = {"generated_at": now.isoformat(), "sample_version": version, "quality": quality,
                "candidate_wallets": len(registry), "discovery_pool_wallets": len(pool),
                "active_sample_wallets": len(sample), "pool_quality": pool_quality,
                "observation_policy": f"minimum {config['observation_days']} days; no same-run promotion"}
    write_json(out / "poc_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Hyperliquid Yobun Hoihoi (public data, read-only)")
    parser.add_argument("command", choices=["poc"])
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/current")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--as-of", help="Pinned ISO-8601 timestamp")
    parser.add_argument("--public-stream", type=Path, action="append")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    manifest = run_poc(args)
    if args.notify:
        q = manifest["quality"]
        message = ("🪤 養分ホイホイ｜Codex作業完了\n\n✅ SUCCESS\n\n"
                   f"Candidates: {manifest['candidate_wallets']} wallets\n"
                   f"Sample: {manifest['active_sample_wallets']} active wallets\n"
                   f"BOT/MM/裁定疑い: {q['bot_suspected'] + q['mm_suspected'] + q['arbitrage_suspected']} flags")
        manifest["discord"] = post_discord(message)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
