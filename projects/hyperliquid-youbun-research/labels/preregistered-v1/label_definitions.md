# Behavior label definitions v1

This document preregisters candidate behavior labels before inspecting the dry-run label counts or any outcome comparison. Version 1 thresholds live in `label_config.json`; they are immutable after the first dry run. A changed threshold must use a new version and retain v1.

## Shared contract

- Status is tri-state: `TRUE`, `FALSE`, or `UNAVAILABLE`.
- Missing required data produces `UNAVAILABLE`, never `FALSE`.
- Labels are non-exclusive. FOMO and Late may overlap.
- Market labels use only the past-only feature file. No exit, PnL, MFE, MAE, or post-entry value is available to those functions.
- Long/Short use one direction-adjusted implementation. `direction_sign = +1` for LONG and `-1` for SHORT.
- Output names add `_LONG` or `_SHORT` when status is TRUE; `REVENGE_CANDIDATE` is side-neutral.

## FOMO_LONG / FOMO_SHORT

All four rules must pass:

1. `direction_sign * return_5m >= 0`
2. `direction_sign * return_15m >= 0.01`
3. `volume_ratio_15m >= 1.5`
4. directional range position is at least `0.8`, where LONG uses `range_position` and SHORT uses `1 - range_position`.

Score is the fraction of four rules passed. Rationale: v1 represents an already-extended 15-minute move with volume expansion near the local range edge. Thresholds are round PoC starting values, not estimated from label frequency or PnL.

## LATE_LONG / LATE_SHORT

All three rules must pass:

1. `direction_sign * return_1h >= 0.02`
2. directional range position is at least `0.85`
3. side-adjusted `breakout_distance >= -0.005`

Score is the fraction of three rules passed. Late emphasizes move progress and location; FOMO emphasizes short acceleration plus volume. Overlap is explicitly allowed.

## AVERAGING_DOWN_LONG / SHORT

For every same-direction add in stable server timestamp order:

- position exists before the fill;
- added quantity / absolute pre-fill position is at least `0.05`;
- LONG add price is at least 5bp below the pre-add weighted average entry, or SHORT add price is at least 5bp above it.

Episode status is TRUE when at least one qualifying adverse add exists. Stored diagnostics are add count, adverse add count, adverse added quantity / initial quantity, and worst adverse price distance. Small adds are ignored as noise, not classified FALSE at fill grain.

## PROFIT_PYRAMIDING_LONG / SHORT

Uses the same 5% size and 5bp price-distance thresholds, but requires an add in the favorable direction: above weighted average entry for LONG and below it for SHORT. It is stored separately from averaging down. One episode may contain both behaviors at different fills.

## REVENGE_CANDIDATE

All conditions must pass:

1. the latest prior non-overlapping episode in the same wallet has `net_pnl < 0`;
2. current entry occurs no more than 60 minutes after that episode exits;
3. current initial notional / previous initial notional is at least `1.25`.

Same coin and side relationship are diagnostics only. This label never asserts emotion or intent. Overlapping positions are not treated as a previous completed episode.

## Excluded v1 labels

- `CROWDING`: unavailable historical OI.
- `TRAPPED`: unavailable historical margin/liquidation state.
- `LIQUIDATION_BEHAVIOR`: insufficient explicit liquidation events.
- `逆指標`: an outcome hypothesis, not a behavior label.

## Measurement plan and guardrails

- The 24-episode dry run checks code, symmetry, missingness, overlap, and reproducibility only.
- No win rate, PnL, profit factor, or counter-trade result is calculated in the dry run.
- Exploratory comparisons require at least 100 labeled and 100 control episodes and must report wallet/coin/time clustering.
- Confirmatory testing requires at least 500 total episodes, at least 50 observations in every tested label-side cell, a held-out time period, fee/Funding inclusion, and multiple-testing control.
- Threshold changes create v2; v1 remains reproducible and is not overwritten.
