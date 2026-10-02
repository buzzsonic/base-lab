from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from scripts.audit_market_coverage import read_csv, write_csv

LABELS = ("fomo", "late", "averaging_down", "profit_pyramiding", "revenge")

def label_counts(rows):
    output = []
    for label in LABELS:
        counts = Counter(row[f"{label}_status"] for row in rows)
        output.append({"label": label, "true": counts["TRUE"], "false": counts["FALSE"], "unavailable": counts["UNAVAILABLE"], "total": len(rows)})
    return output

def group_summary(rows, field):
    groups = defaultdict(list)
    for row in rows: groups[row[field]].append(row)
    output = []
    for value, items in sorted(groups.items()):
        result = {field: value, "episodes": len(items)}
        for label in LABELS:
            result[f"{label}_true"] = sum(row[f"{label}_status"] == "TRUE" for row in items)
            result[f"{label}_unavailable"] = sum(row[f"{label}_status"] == "UNAVAILABLE" for row in items)
        output.append(result)
    return output

def overlap_rows(rows):
    counts = Counter()
    for row in rows:
        active = tuple(label for label in LABELS if row[f"{label}_status"] == "TRUE")
        counts["+".join(active) if active else "NONE"] += 1
    return [{"true_label_pattern": pattern, "episodes": count} for pattern, count in sorted(counts.items())]

def episode_rows(rows):
    fields = ["episode_id", "account_alias", "coin", "side", "entry_time", "config_version"]
    for suffix in ("status", "score", "triggered_rules", "missing_required_features"):
        fields += [f"{label}_{suffix}" for label in LABELS]
    return [{field: row[field] for field in fields} for row in rows]

def write_report(path: Path, rows):
    counts = {row["label"]: row for row in label_counts(rows)}
    lines = ["# Exploratory behavior distribution v1", "", "## Scope", "", "Outcome-free distribution and availability summary for 24 episodes. No PnL, win rate, PF, MFE/MAE, post-entry return, or counter-trade result is included.", "", "| label | TRUE | FALSE | UNAVAILABLE |", "|---|---:|---:|---:|"]
    for label in LABELS:
        item = counts[label]
        lines.append(f"| {label} | {item['true']} | {item['false']} | {item['unavailable']} |")
    lines += ["", "## Boundary", "", "This output establishes only label distribution and missingness. Wallet, coin, side, and overlap summaries are descriptive quality checks. v1 thresholds remain frozen.", "", "## Next", "", "Review all TRUE rows and stratified FALSE rows without outcomes, then design expansion to 100–500 accounts and thousands of episodes while preserving reconstruction error zero."]
    path.write_text("\n".join(lines) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_csv(args.labels)
    if len(rows) != 24 or len({row["episode_id"] for row in rows}) != 24: raise RuntimeError("expected 24 unique dry-run episodes")
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "label_counts.csv", label_counts(rows))
    write_csv(args.output / "episode_labels.csv", episode_rows(rows))
    write_csv(args.output / "wallet_label_summary.csv", group_summary(rows, "account_alias"))
    write_csv(args.output / "coin_label_summary.csv", group_summary(rows, "coin"))
    write_csv(args.output / "side_label_summary.csv", group_summary(rows, "side"))
    write_csv(args.output / "label_overlaps.csv", overlap_rows(rows))
    write_report(args.output / "README.md", rows)

if __name__ == "__main__": main()
