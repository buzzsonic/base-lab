# Behavior label v1 dry run

## Scope

This dry run validates implementation, availability, symmetry, overlap support, and deterministic output for 24 episodes. It contains no PnL, win/loss, profit factor, MFE/MAE, post-entry return, or counter-trade result.

| label | TRUE | FALSE | UNAVAILABLE |
|---|---:|---:|---:|
| fomo | 1 | 23 | 0 |
| late | 2 | 22 | 0 |
| averaging_down | 4 | 20 | 0 |
| profit_pyramiding | 8 | 16 | 0 |
| revenge | 4 | 14 | 6 |

Observed FOMO+Late overlap: 0. The schema and synthetic test allow overlap even though this small dry run produced none.

Revenge `UNAVAILABLE` rows lack a prior non-overlapping completed episode in the observed eligible history. They are not treated as FALSE.

## Decision

PASS for label-pipeline mechanics only. Version 1 thresholds are now frozen. These counts are not evidence about profitability, causality, psychology, or inverse-signal value.
