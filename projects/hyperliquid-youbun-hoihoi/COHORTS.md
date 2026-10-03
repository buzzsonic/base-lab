# Cohort contract

## Current cohort

- Path on `data`: `outputs/current/`
- Purpose: continue the original 100-wallet observation without changing membership.
- Promotion: only after at least seven elapsed days and seven distinct successful JST observation dates.

## Shadow cohort: `stratified-20261003`

- Path on `data`: `outputs/cohorts/stratified-20261003/`
- Source: isolated run `37116104107`, artifact `youbun-hoihoi-poc-preview-37116104107-1`.
- Initial membership: 100 selected wallets from a fresh 200-wallet pool.
- Purpose: test whether improved completeness and diversity persist for seven JST observation days.
- Mutation boundary: its registry, pool, fill checkpoints, raw cache, manifest, sample, and review files stay under the cohort path. It must never write to `outputs/current/`.
- Failure policy: missing seed files, API gaps, same-ms saturation, request-budget exhaustion, and retention gaps fail closed. They are not successful observation dates and do not permit promotion.
- Replacement policy: the shadow cohort cannot replace or merge with the current cohort automatically. A reviewed comparison and an explicit decision are required after the observation gate.

## Scheduled observation

`.github/workflows/youbun-hoihoi-shadow-observe.yml` runs daily at 03:20 JST and can also be dispatched manually. It uses the same `youbun-hoihoi-data` concurrency group and rebase-retry push helper as the current cohort, so the two writers serialize on the shared `data` branch.

The workflow requires these seed files:

- `cohort_manifest.json`
- `discovery_pool.parquet`
- `wallet_registry.parquet`

It then creates and updates the cohort-local `fill-checkpoints/`, `raw-cache/`, `research_sample.parquet`, `poc_manifest.json`, and review outputs.

## First runtime validation

- Run: `37120774019` success
- Data commit: `bb4709f`
- Persisted state: registry 100, pool 200, checkpoints 100, sample 0
- Successful observation dates: 98 wallets at one day, 2 at zero
- Live completeness: 97 complete, 3 incomplete; one previously complete wallet became incomplete and did not gain a successful date
- Current-cohort isolation: the `outputs/current/` tree hash remained `96e57802da37182ec82f0d5461cdbbf3c257d992` before and after the shadow commit
