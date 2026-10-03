from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def fill_extent(data: Path, wallet: str, start_ms: int, end_ms: int) -> tuple[int, int | None, int | None]:
    path = data / "raw" / f"fills_{wallet}_{start_ms}_{end_ms}.json"
    rows = json.loads(path.read_text())
    times = [int(row["time"]) for row in rows]
    return len(rows), min(times, default=None), max(times, default=None)


def audit(sample: Path, original: Path, corrected: Path, output: Path,
          start_ms: int, end_ms: int) -> dict:
    sample_rows = read_csv(sample)
    quality = {row["anon_wallet_id"]: row for row in read_csv(corrected / "quality" / "account_quality.csv")}
    rows = []
    for account in sample_rows:
        alias = account["anon_wallet_id"]
        wallet = account["wallet"].lower()
        old_extent = fill_extent(original, wallet, start_ms, end_ms)
        new_extent = fill_extent(corrected, wallet, start_ms, end_ms)
        q = quality[alias]
        comparable = (new_extent[0] >= old_extent[0] and
                      new_extent[1] == old_extent[1] and new_extent[2] == old_extent[2])
        reasons = []
        if not comparable:
            reasons.append("refetch_coverage_loss")
        if int(q["perp_fills"]) == 0:
            reasons.append("no_perp_fills")
        if int(q["continuity_errors"]) > 0:
            reasons.append("twap_retention_gap" if int(q["twap_rows"]) > 0 else "unrecoverable_fill_gap")
        if int(q["quantity_mismatches"]) > 0:
            reasons.append("quantity_mismatch")
        if int(q["completed_uncensored"]) == 0:
            reasons.append("no_completed_episode")
        rows.append({
            "anon_wallet_id": alias, "split": account["split"],
            "original_fill_rows": old_extent[0], "corrected_fill_rows": new_extent[0],
            "same_fixed_window_coverage": comparable, "twap_rows": q["twap_rows"],
            "perp_fills": q["perp_fills"], "episodes": q["episodes"],
            "completed_uncensored": q["completed_uncensored"],
            "quantity_mismatches": q["quantity_mismatches"],
            "continuity_errors": q["continuity_errors"],
            "eligible": not reasons, "exclusion_reasons": ";".join(reasons),
        })
    output.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (output / "wallet_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    reason_counts = Counter(reason for row in rows for reason in row["exclusion_reasons"].split(";") if reason)
    cause_rows = [{"reason": reason, "wallets": count, "rate": f"{count / len(rows):.4f}"}
                  for reason, count in sorted(reason_counts.items())]
    with (output / "cause_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["reason", "wallets", "rate"], lineterminator="\n")
        writer.writeheader(); writer.writerows(cause_rows)
    eligible = [row for row in rows if row["eligible"]]
    summary = {
        "sample_wallets": len(rows), "coverage_comparable_wallets": sum(row["same_fixed_window_coverage"] for row in rows),
        "eligible_wallets": len(eligible), "excluded_wallets": len(rows) - len(eligible),
        "eligible_completed_episodes": sum(int(row["completed_uncensored"]) for row in eligible),
        "eligible_quantity_mismatches": sum(int(row["quantity_mismatches"]) for row in eligible),
        "eligible_continuity_errors": sum(int(row["continuity_errors"]) for row in eligible),
        "reason_counts": dict(sorted(reason_counts.items())),
        "gate": "STOP_API_RETENTION_REQUIRES_FORWARD_COLLECTION_DESIGN",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--corrected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.sample, args.original, args.corrected, args.output,
                           args.start_ms, args.end_ms), indent=2))


if __name__ == "__main__":
    main()
