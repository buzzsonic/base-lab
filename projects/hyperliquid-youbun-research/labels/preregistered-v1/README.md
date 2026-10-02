# Preregistered behavior labels v1

This directory freezes the first candidate definitions for FOMO, Late entry, averaging down, profit pyramiding, and Revenge candidate before dry-run counts or outcomes are inspected.

Files:

- `label_definitions.md`: human-readable definitions, exclusions, and measurement guardrails
- `label_config.json`: immutable v1 thresholds and required inputs
- `label_schema.json`: tri-state output contract
- `dry_run_labels.csv`: 24-episode implementation/availability output; no outcome columns
- `dry_run_summary.csv`: label status counts only
- `dry_run_report.md`: scope-limited dry-run interpretation and gate decision

The dry run is not evidence that a behavior wins, loses, predicts price, or should be traded against. Historical OI, margin, liquidation distance, and liquidation-state labels remain out of scope.
