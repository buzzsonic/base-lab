from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


SAMPLE_VERSION = "pilot-100-v1"
ALGORITHM_VERSION = "public-trades-stratified-v1"
MAJOR = {"BTC", "ETH"}


def stable_hash(seed: str, purpose: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{purpose}|{value}".encode()).hexdigest()


def time_band(timestamp_ms: int) -> str:
    hour_jst = (timestamp_ms // 3_600_000 + 9) % 24
    if hour_jst < 6:
        return "jst_00_05"
    if hour_jst < 12:
        return "jst_06_11"
    if hour_jst < 18:
        return "jst_12_17"
    return "jst_18_23"


def read_trades(path: Path, start_ms: int, small_alts: set[str]) -> dict[str, dict]:
    wallets: dict[str, dict] = {}
    seen: set[tuple[str, int, str]] = set()
    with path.open(errors="replace") as handle:
        for line in handle:
            envelope = json.loads(line)
            if envelope.get("channel") != "trades":
                continue
            wire = json.loads(envelope["wire"])
            for trade in wire.get("data", []):
                timestamp = int(trade.get("time") or 0)
                if timestamp < start_ms:
                    continue
                coin = str(trade.get("coin") or "")
                key = (coin, timestamp, str(trade.get("tid") or ""))
                if key in seen:
                    continue
                seen.add(key)
                notional = Decimal(str(trade["px"])) * Decimal(str(trade["sz"]))
                symbol_group = "major" if coin in MAJOR else "small_alt" if coin in small_alts else "alt"
                for wallet in trade.get("users") or []:
                    wallet = str(wallet).lower()
                    item = wallets.setdefault(wallet, {
                        "event_count": 0, "notionals": [], "symbols": Counter(),
                        "activity": Counter(), "first_seen": timestamp, "last_seen": timestamp,
                    })
                    item["event_count"] += 1
                    item["notionals"].append(notional)
                    item["symbols"][symbol_group] += 1
                    item["activity"][time_band(timestamp)] += 1
                    item["first_seen"] = min(item["first_seen"], timestamp)
                    item["last_seen"] = max(item["last_seen"], timestamp)
    return wallets


def median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def classify(wallet: str, item: dict) -> dict:
    count = item["event_count"]
    frequency = "low" if count <= 2 else "medium" if count <= 10 else "high"
    median_notional = median(item["notionals"])
    size = "small" if median_notional < 100 else "medium" if median_notional < 1_000 else "large"
    symbol = item["symbols"].most_common(1)[0][0]
    activity = item["activity"].most_common(1)[0][0]
    stratum = f"size={size}|frequency={frequency}|symbol={symbol}|activity={activity}"
    return {
        "wallet": wallet, "source": "hoihoi_public_trades_runtime",
        "stratum": stratum, "size_band": size, "frequency_band": frequency,
        "symbol_tendency": symbol, "activity_band": activity,
        "event_count": count, "median_notional": str(median_notional),
    }


def select(rows: list[dict], seed: str, limit: int = 100) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row["stratum"]].append(row)
    for stratum, bucket in buckets.items():
        bucket.sort(key=lambda row: stable_hash(seed, f"select:{stratum}", row["wallet"]))
    keys = sorted(buckets)
    chosen: list[dict] = []
    while keys and len(chosen) < limit:
        for key in list(keys):
            if not buckets[key]:
                keys.remove(key)
                continue
            chosen.append(buckets[key].pop(0))
            if len(chosen) == limit:
                break
    if len(chosen) != limit:
        raise ValueError(f"candidate universe has only {len(chosen)} wallets; need {limit}")
    split_order = sorted(chosen, key=lambda row: stable_hash(seed, "split", row["wallet"]))
    splits = {row["wallet"]: ("exploratory" if i < 60 else "validation" if i < 80 else "held_out")
              for i, row in enumerate(split_order)}
    alias_order = sorted(chosen, key=lambda row: stable_hash(seed, "alias", row["wallet"]))
    aliases = {row["wallet"]: f"P{i:03d}" for i, row in enumerate(alias_order, 1)}
    output = []
    for row in chosen:
        output.append({
            "wallet": row["wallet"], "anon_wallet_id": aliases[row["wallet"]],
            "source": row["source"], "stratum": row["stratum"],
            "size_band": row["size_band"], "frequency_band": row["frequency_band"],
            "symbol_tendency": row["symbol_tendency"], "activity_band": row["activity_band"],
            "split": splits[row["wallet"]],
            "inclusion_reason": "deterministic round-robin coverage of outcome-free public Trades strata",
            "exclusion_reason": "", "sample_version": SAMPLE_VERSION,
        })
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(source: Path, output: Path, source_commit: str, source_path: str,
          fixed_start: str, fixed_end: str, small_alts: set[str], seed: str) -> list[dict]:
    start_ms = int(datetime.fromisoformat(fixed_start.replace("Z", "+00:00")).timestamp() * 1000)
    universe = read_trades(source, start_ms, small_alts)
    classified = [classify(wallet, item) for wallet, item in universe.items()]
    selected = select(classified, seed)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "sampling_manifest.csv", selected)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    strata = Counter(row["stratum"] for row in selected)
    manifest = {
        "schema_version": 1, "sample_version": SAMPLE_VERSION,
        "source_project": "projects/hyperliquid-youbun-hoihoi", "source_branch": "data",
        "source_commit": source_commit, "source_data_version": "discovery-runtime-20261002T023843Z",
        "fixed_start_time": fixed_start, "fixed_end_time": fixed_end,
        "source_files": [{"path": source_path, "sha256": source_sha}],
        "selection_seed": seed, "selection_algorithm_version": ALGORITHM_VERSION,
        "candidate_wallets_after_fixed_start": len(universe), "selected_wallets": len(selected),
        "split_counts": dict(sorted(Counter(row["split"] for row in selected).items())),
        "strata_counts": dict(sorted(strata.items())),
        "sampling_inputs": ["trade time", "trade price", "trade size", "coin", "public trade participants"],
        "prohibited_sampling_inputs": ["PnL", "ROI", "win/loss", "episode outcome", "behavior labels"],
    }
    (output / "source_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "README.md").write_text(
        "# Pilot 100 sampling v1\n\n"
        "Hoihoiの固定済み公開Trades runtimeを読み取り専用sourceとして、実収集開始後のtradeだけから100 walletを固定した。"
        "同一tradeは`coin/time/tid`で重複排除し、size・frequency・symbol・JST activity strataをround-robinした。\n\n"
        "- outcome / PnL / ROI / behavior labelは抽出に不使用\n"
        "- splitは収集前にexploratory 60 / validation 20 / held_out 20へ固定\n"
        "- wallet差替えは禁止。技術除外はmanifestを変更せず別途記録する\n"
        "- source rawはHoihoi data branchの固定commitに保持し、本ディレクトリへ複製しない\n"
    )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--fixed-start", required=True)
    parser.add_argument("--fixed-end", required=True)
    parser.add_argument("--small-alts", required=True)
    parser.add_argument("--seed", default="youbun-pilot-100-v1-20261002")
    args = parser.parse_args()
    build(args.source, args.output, args.source_commit, args.source_path,
          args.fixed_start, args.fixed_end, set(args.small_alts.split(",")), args.seed)


if __name__ == "__main__":
    main()
