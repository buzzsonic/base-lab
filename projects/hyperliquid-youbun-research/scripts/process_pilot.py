from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from src.poc import merge_fills, write_csv
from src.reconstruct import attribute_funding, continuity_errors, quality_summary, reconstruct_episodes


def read_manifest(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def process(manifest: Path, data: Path, start_ms: int, end_ms: int) -> dict:
    accounts = read_manifest(manifest)
    raw = data / "raw"
    processed = data / "processed"
    quality = data / "quality"
    processed.mkdir(parents=True, exist_ok=True)
    quality.mkdir(parents=True, exist_ok=True)
    episodes_out, account_out = [], []
    for account in accounts:
        wallet = account["wallet"].lower()
        fills = load(raw / f"fills_{wallet}_{start_ms}_{end_ms}.json")
        twap = load(raw / f"twap_fills_{wallet}_{start_ms}_{end_ms}.json")
        funding = load(raw / f"funding_{wallet}_{start_ms}_{end_ms}.json")
        merged, twap_added = merge_fills(fills, twap)
        perp = [row for row in merged if not str(row.get("coin", "")).startswith("@")]
        episodes = reconstruct_episodes(wallet, perp)
        attribute_funding(episodes, funding, end_ms)
        episodes_out.extend(episode.row() for episode in episodes)
        base = quality_summary(episodes)
        base.update({
            "anon_wallet_id": account["anon_wallet_id"], "split": account["split"],
            "fills": len(fills), "twap_rows": len(twap), "twap_added": twap_added,
            "perp_fills": len(perp), "funding_rows": len(funding),
            "continuity_errors": continuity_errors(perp),
            "twap_endpoint_capped": len(twap) >= 2000,
            "fills_safety_cap_hit": len(fills) >= 200_000,
            "funding_safety_cap_hit": len(funding) >= 50_000,
        })
        base["eligible_for_reconstruction"] = (
            base["perp_fills"] > 0 and base["quantity_mismatches"] == 0
            and base["continuity_errors"] == 0 and not base["twap_endpoint_capped"]
            and not base["fills_safety_cap_hit"] and not base["funding_safety_cap_hit"]
        )
        account_out.append(base)
    write_csv(processed / "position_episodes.csv", episodes_out)
    write_csv(quality / "account_quality.csv", account_out)
    summary = {
        "requested_wallets": len(accounts), "processed_wallets": len(account_out),
        "raw_fills": sum(row["fills"] for row in account_out),
        "perp_fills": sum(row["perp_fills"] for row in account_out),
        "funding_rows": sum(row["funding_rows"] for row in account_out),
        "twap_rows": sum(row["twap_rows"] for row in account_out),
        "episodes": len(episodes_out),
        "completed_uncensored": sum(row["completed_uncensored"] for row in account_out),
        "quantity_mismatches": sum(row["quantity_mismatches"] for row in account_out),
        "continuity_errors": sum(row["continuity_errors"] for row in account_out),
        "eligible_wallets": sum(row["eligible_for_reconstruction"] for row in account_out),
        "twap_cap_wallets": sum(row["twap_endpoint_capped"] for row in account_out),
        "fills_safety_cap_wallets": sum(row["fills_safety_cap_hit"] for row in account_out),
        "funding_safety_cap_wallets": sum(row["funding_safety_cap_hit"] for row in account_out),
        "zero_perp_fill_wallets": sum(row["perp_fills"] == 0 for row in account_out),
    }
    (quality / "pilot_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(process(args.manifest, args.data, args.start_ms, args.end_ms), indent=2))


if __name__ == "__main__":
    main()
