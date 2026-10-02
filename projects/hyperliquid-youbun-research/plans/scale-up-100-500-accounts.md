# Scale-up plan: 100–500 accounts and thousands of episodes

## Cohort and periods

- Sample 500 candidate accounts across monthly volume, ROI/loss depth, activity, holding-time, market-cap exposure, and fill-frequency strata; do not select only leaderboard losers.
- Freeze a 100-account pilot first. Expand to 500 only if reconstruction/accounting error remains zero and exclusion rates are reported.
- Separate time windows before collection: exploratory development 60%, validation 20%, held-out confirmation 20%. Never tune v1 on the held-out window.

## Collection contract

- Store raw regular fills, TWAP slices, Funding, fetch metadata, caps, and exact server order before transformations.
- Collect 5-minute candles continuously so the 5,000-bar API limit does not erase entry windows. Store gaps and never forward-fill.
- Keep historical mark/OI NULL unless directly observed by the realtime collector or verified archive rows.
- Pin retrieval end times and retain raw-response hashes for deterministic reruns.

## Account and episode gates

- Require perp fills, uncapped TWAP, continuity errors=0, quantity mismatches=0, completed zero-to-zero episode, and no left censoring.
- Reconcile boundaries, quantities, closedPnl, fee, Funding, and net PnL at episode grain. Any material mismatch excludes the account until repaired.
- Report eligible/excluded counts and reasons by sampling stratum; exclusions must not silently change cohort composition.

## Sample targets

- Operational target: at least 2,000 eligible completed episodes after exclusions.
- Before outcome comparison: at least 100 labeled and 100 control episodes for each exploratory label comparison.
- Confirmatory target: at least 500 total held-out episodes and at least 50 observations in every tested label-side cell.
- If a label remains sparse, extend time/accounts; do not loosen frozen v1 thresholds based on observed outcomes.

## Statistical guardrails

- Cluster uncertainty by wallet and time; report coin/side concentration.
- Include fee and Funding in outcomes, keep multiple-testing correction, and publish missingness/exclusion rates.
- Compare v1 on held-out data before proposing v2. Any v2 is evaluated on a new holdout.
- No automated trading, wallet exposure, or psychological claims.

## Promotion gates

1. 100-account pilot: reconstruction and accounting error zero; candle-window coverage quantified.
2. 500-account expansion: same gates plus stable exclusion rates across strata.
3. Exploratory outcome analysis: minimum cell sizes met; no held-out data used for tuning.
4. Confirmatory analysis: preregistered tests, held-out window, clustered inference, costs included.
