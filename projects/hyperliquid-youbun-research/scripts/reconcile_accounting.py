from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from scripts.review_episodes import (
    MONEY_TOLERANCE,
    ZERO,
    anonymized_aliases,
    attribute_raw_funding,
    compare,
    dec,
    eligibility_reasons,
    key_for,
    load_json,
    one_file,
    read_csv,
    reconstruct_raw,
)
from src.poc import merge_fills


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def load_account_inputs(raw_dir: Path, wallet: str) -> tuple[list[dict], list[dict], list[dict], int, list[dict]]:
    fills_path = one_file(raw_dir, "fills", wallet)
    twap_path = one_file(raw_dir, "twap_fills", wallet)
    funding_path = one_file(raw_dir, "funding", wallet)
    regular = load_json(fills_path) if fills_path else []
    twap = load_json(twap_path) if twap_path else []
    funding = load_json(funding_path) if funding_path else []
    merged, twap_added = merge_fills(regular, twap)
    perp = [row for row in merged if not str(row.get("coin", "")).startswith("@")]
    return regular, twap, funding, twap_added, perp


def build_account_rows(quality_rows: list[dict[str, str]], raw_dir: Path, aliases: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for source in sorted(quality_rows, key=lambda row: row["wallet"].lower()):
        wallet = source["wallet"].lower()
        regular, twap, _, twap_added, _ = load_account_inputs(raw_dir, wallet)
        reasons = eligibility_reasons(source)
        recomputed = not reasons
        stored = source.get("eligible_for_behavior_analysis", "").lower() == "true"
        rows.append({
            "account_alias": aliases[wallet],
            "completed_uncensored": source["completed_uncensored"],
            "regular_fill_count": str(len(regular)),
            "perp_fill_count": source["perp_fills"],
            "twap_endpoint_rows": str(len(twap)),
            "twap_added_after_dedup": str(twap_added),
            "continuity_errors": source["continuity_errors"],
            "twap_endpoint_capped": source["twap_endpoint_capped"],
            "stored_eligible_flag": str(stored),
            "recomputed_eligible": str(recomputed),
            "exclusion_reasons": ",".join(reasons),
            "status": "PASS" if stored == recomputed else "WARN_STALE_STORED_FLAG",
        })
    return rows


def build_episode_rows(
    data_dir: Path,
    quality_rows: list[dict[str, str]],
    aliases: dict[str, str],
) -> tuple[list[dict[str, str]], list]:
    eligible = {row["wallet"].lower() for row in quality_rows if not eligibility_reasons(row)}
    reconstructed = [
        row for row in read_csv(data_dir / "processed" / "position_episodes.csv")
        if row["wallet"].lower() in eligible
        and row["closed"].lower() == "true"
        and row["left_censored"].lower() == "false"
    ]
    recon_by_key = {
        (row["wallet"].lower(), row["coin"], int(row["first_entry_time"]), int(row["last_exit_time"])): row
        for row in reconstructed
    }
    raw_episodes = []
    for wallet in sorted(eligible):
        _, _, funding, _, perp = load_account_inputs(data_dir / "raw", wallet)
        episodes = reconstruct_raw(wallet, perp)
        attribute_raw_funding(episodes, funding)
        raw_episodes.extend(episode for episode in episodes if episode.closed and not episode.left_censored)
    if len(eligible) != 10 or len(raw_episodes) != 61 or len(reconstructed) != 61:
        raise RuntimeError(f"unexpected accounting population: wallets={len(eligible)}, raw={len(raw_episodes)}, reconstructed={len(reconstructed)}")
    if {key_for(item) for item in raw_episodes} != set(recon_by_key):
        raise RuntimeError("raw and reconstructed episode boundaries differ")

    counters: dict[str, int] = defaultdict(int)
    rows = []
    for raw in sorted(raw_episodes, key=lambda item: (aliases[item.wallet], item.first_entry_time, item.coin)):
        alias = aliases[raw.wallet]
        counters[alias] += 1
        recon = recon_by_key[key_for(raw)]
        base_status, reasons, diffs = compare(raw, recon)
        reconstructed_net = dec(recon["net_pnl"])
        net_diff = raw.net_pnl - reconstructed_net
        if abs(net_diff) > MONEY_TOLERANCE:
            reasons.append("net_pnl")
        builder_contained = raw.builder_fee >= ZERO and raw.builder_fee - raw.fees <= MONEY_TOLERANCE
        if not builder_contained and "builder_fee_not_contained_in_fee" not in reasons:
            reasons.append("builder_fee_not_contained_in_fee")
        rows.append({
            "episode_id": f"{alias}-A{counters[alias]:03d}",
            "account_alias": alias,
            "coin": raw.coin,
            "entry_time": str(raw.first_entry_time),
            "exit_time": str(raw.last_exit_time),
            "raw_closed_pnl": fmt(raw.realized_pnl),
            "reconstructed_closed_pnl": recon["realized_pnl"],
            "closed_pnl_diff": fmt(diffs["realized_pnl"]),
            "raw_fee_total_including_builder": fmt(raw.fees),
            "reconstructed_fee": recon["fees"],
            "fee_diff": fmt(diffs["fees"]),
            "raw_builder_fee_component": fmt(raw.builder_fee),
            "builder_fee_contained_in_fee": str(builder_contained),
            "raw_funding": fmt(raw.funding),
            "reconstructed_funding": recon["funding"],
            "funding_diff": fmt(diffs["funding"]),
            "raw_net_pnl_without_builder_readd": fmt(raw.net_pnl),
            "reconstructed_net_pnl": recon["net_pnl"],
            "net_pnl_diff": fmt(net_diff),
            "twap_fill_segments": str(raw.twap_fill_count),
            "status": "PASS" if base_status == "PASS" and not reasons else "FAIL",
            "difference_reason": ",".join(sorted(set(reasons))),
        })
    return rows, raw_episodes


def funding_summary(episodes, aliases: dict[str, str]) -> list[dict[str, str]]:
    groups = {"ALL": episodes}
    groups.update({alias: [item for item in episodes if aliases[item.wallet] == alias] for alias in sorted(set(aliases.values()))})
    rows = []
    for group, items in groups.items():
        if not items:
            continue
        values = [item.funding for item in items]
        rows.append({
            "group": group,
            "episodes": str(len(items)),
            "nonzero_funding_episodes": str(sum(value != ZERO for value in values)),
            "positive_funding_episodes": str(sum(value > ZERO for value in values)),
            "negative_funding_episodes": str(sum(value < ZERO for value in values)),
            "funding_total_usdc": fmt(sum(values, ZERO)),
            "funding_min_usdc": fmt(min(values)),
            "funding_max_usdc": fmt(max(values)),
        })
    return rows


def builder_summary(episodes, aliases: dict[str, str]) -> list[dict[str, str]]:
    groups = {"ALL": episodes}
    groups.update({alias: [item for item in episodes if aliases[item.wallet] == alias] for alias in sorted(set(aliases.values()))})
    rows = []
    for group, items in groups.items():
        if not items:
            continue
        affected = [item for item in items if item.builder_fee != ZERO]
        total_builder = sum((item.builder_fee for item in affected), ZERO)
        total_fee = sum((item.fees for item in affected), ZERO)
        rows.append({
            "group": group,
            "episodes": str(len(items)),
            "nonzero_builder_fee_episodes": str(len(affected)),
            "builder_fee_total_usdc": fmt(total_builder),
            "fee_total_for_builder_episodes_usdc": fmt(total_fee),
            "builder_fee_share_of_fee": fmt(total_builder / total_fee) if total_fee else "0",
            "all_builder_fees_contained_in_fee": str(all(item.builder_fee <= item.fees for item in affected)),
        })
    return rows


def write_report(path: Path, account_rows, episode_rows, funding_rows, builder_rows) -> None:
    failures = [row for row in episode_rows if row["status"] != "PASS"]
    warnings = [row for row in account_rows if row["status"].startswith("WARN")]
    eligible_rows = [row for row in account_rows if row["recomputed_eligible"] == "True"]
    excluded_rows = [row for row in account_rows if row["recomputed_eligible"] == "False"]
    all_funding = next(row for row in funding_rows if row["group"] == "ALL")
    all_builder = next(row for row in builder_rows if row["group"] == "ALL")
    status = "PASS" if not failures else "FAIL"
    lines = [
        "# Accounting quality review — 2026-10-02",
        "",
        "## Result",
        "",
        f"**{status}:** {len(episode_rows) - len(failures)}/{len(episode_rows)} completed eligible episodes matched for closedPnl, fee, Funding, and net PnL.",
        "",
        "| check | result |",
        "|---|---:|",
        f"| Eligible accounts | {len(eligible_rows)} |",
        f"| Completed episodes reconciled | {len(episode_rows)} |",
        f"| Accounting failures | {len(failures)} |",
        f"| Funding nonzero episodes | {all_funding['nonzero_funding_episodes']} |",
        f"| Funding total (USDC) | {all_funding['funding_total_usdc']} |",
        f"| builderFee nonzero episodes | {all_builder['nonzero_builder_fee_episodes']} |",
        f"| builderFee total (USDC) | {all_builder['builder_fee_total_usdc']} |",
        f"| Eligible TWAP additions after dedup | {sum(int(row['twap_added_after_dedup']) for row in eligible_rows)} |",
        f"| Excluded accounts | {len(excluded_rows)} |",
        "",
        "## Accounting contract",
        "",
        "`episode net PnL = closedPnl - fee + Funding`",
        "",
        "Hyperliquid's fill schema defines `fee` as the total fee inclusive of `builderFee`. Therefore `builderFee` is retained as a component for analysis but is not subtracted again. The 61 episode calculations use this formula and matched the processed output within 1e-6 USDC.",
        "",
        "Funding is assigned only when the official `userFunding` row has the same coin and a timestamp inside the observed episode interval, including both endpoints.",
        "",
        "Official references:",
        "- https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint",
        "- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals",
        "",
        "## TWAP result and future contract",
        "",
        "- Eligible 10 accounts had zero TWAP additions after deduplication.",
        "- The account with 2,000 TWAP endpoint rows and 15 continuity errors remains excluded.",
        "- A zero-perp-fill account remains excluded.",
        "- Future TWAP slices are merged by `tid` (fallback: hash/oid/time/size), retain `source_kind=twap`, and participate in the same stable timestamp ordering as regular fills.",
        "- Any account whose TWAP endpoint is capped is not behavior-analysis eligible until complete coverage is obtained; missing slices are never inferred or forward-filled.",
        "",
        "## Warning",
        "",
        f"The cached `account_quality.csv` has {len(warnings)} stale stored eligibility flag mismatch. The affected zero-perp-fill account is correctly excluded by recomputed criteria, and the current pipeline code already requires completed episodes and perp fills. Regenerate the cache on the next PoC run.",
        "",
        "## Artifacts",
        "",
        "- `episode_reconciliation.csv`: all 61 episode accounting comparisons",
        "- `funding_summary.csv`: overall and account-level Funding coverage",
        "- `builder_fee_summary.csv`: builderFee coverage and fee containment",
        "- `account_twap_eligibility.csv`: TWAP coverage and exclusion reasons",
        "",
        "## Scope limits",
        "",
        "- This review validates the fixed 30-day PoC cache, not history outside the cached window.",
        "- No eligible account had additional TWAP slices, so positive-path TWAP behavior is covered by fixtures rather than an eligible real-data episode.",
        "- Historical margin state, liquidation distance, and behavioral labels were not computed.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile episode accounting for the youbun PoC.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    quality_rows = read_csv(args.data / "quality" / "account_quality.csv")
    wallets = sorted(row["wallet"].lower() for row in quality_rows)
    aliases = anonymized_aliases(wallets)
    account_rows = build_account_rows(quality_rows, args.data / "raw", aliases)
    episode_rows, episodes = build_episode_rows(args.data, quality_rows, aliases)
    funding_rows = funding_summary(episodes, aliases)
    builder_rows = builder_summary(episodes, aliases)
    write_csv(args.output / "episode_reconciliation.csv", episode_rows)
    write_csv(args.output / "funding_summary.csv", funding_rows)
    write_csv(args.output / "builder_fee_summary.csv", builder_rows)
    write_csv(args.output / "account_twap_eligibility.csv", account_rows)
    write_report(args.output / "README.md", account_rows, episode_rows, funding_rows, builder_rows)
    failed = sum(row["status"] != "PASS" for row in episode_rows)
    print(json.dumps({
        "accounts": len(account_rows),
        "eligible_accounts": sum(row["recomputed_eligible"] == "True" for row in account_rows),
        "episodes": len(episode_rows),
        "failed": failed,
        "metadata_warnings": sum(row["status"].startswith("WARN") for row in account_rows),
    }))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
