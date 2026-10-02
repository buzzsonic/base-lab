# Accounting quality review — 2026-10-02

## Result

**PASS:** 61/61 completed eligible episodes matched for closedPnl, fee, Funding, and net PnL.

| check | result |
|---|---:|
| Eligible accounts | 10 |
| Completed episodes reconciled | 61 |
| Accounting failures | 0 |
| Funding nonzero episodes | 44 |
| Funding total (USDC) | -1004.713607 |
| builderFee nonzero episodes | 9 |
| builderFee total (USDC) | 565.678405 |
| Eligible TWAP additions after dedup | 0 |
| Excluded accounts | 2 |

## Accounting contract

`episode net PnL = closedPnl - fee + Funding`

Hyperliquid's fill schema defines `fee` as the total fee inclusive of `builderFee`. Therefore `builderFee` is retained as a component for analysis but is not subtracted again. The 61 episode calculations use this formula and matched the processed output within 1e-6 USDC.

Funding is assigned only when the official `userFunding` row has the same coin and a timestamp inside the observed episode interval, including both endpoints.

Official references:
- https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals

## TWAP result and future contract

- Eligible 10 accounts had zero TWAP additions after deduplication.
- The account with 2,000 TWAP endpoint rows and 15 continuity errors remains excluded.
- A zero-perp-fill account remains excluded.
- Future TWAP slices are merged by `tid` (fallback: hash/oid/time/size), retain `source_kind=twap`, and participate in the same stable timestamp ordering as regular fills.
- Any account whose TWAP endpoint is capped is not behavior-analysis eligible until complete coverage is obtained; missing slices are never inferred or forward-filled.

## Warning

The cached `account_quality.csv` has 1 stale stored eligibility flag mismatch. The affected zero-perp-fill account is correctly excluded by recomputed criteria, and the current pipeline code already requires completed episodes and perp fills. Regenerate the cache on the next PoC run.

## Artifacts

- `episode_reconciliation.csv`: all 61 episode accounting comparisons
- `funding_summary.csv`: overall and account-level Funding coverage
- `builder_fee_summary.csv`: builderFee coverage and fee containment
- `account_twap_eligibility.csv`: TWAP coverage and exclusion reasons

## Scope limits

- This review validates the fixed 30-day PoC cache, not history outside the cached window.
- No eligible account had additional TWAP slices, so positive-path TWAP behavior is covered by fixtures rather than an eligible real-data episode.
- Historical margin state, liquidation distance, and behavioral labels were not computed.
