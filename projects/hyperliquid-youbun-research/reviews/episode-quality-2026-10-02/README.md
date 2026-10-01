# Episode reconstruction visual review — 2026-10-02

## Scope and grain

- Population: 61 completed, uncensored episodes from eligible accounts.
- Reviewed sample: 20 episodes; each row is one zero-to-zero position episode.
- Wallets are replaced with deterministic aliases; raw wallet addresses are not included.
- This is a reconstruction-quality review only. No FOMO/Late/Nanpin/Revenge labels were computed.

## Selection

A deterministic quota-guided selection covered outcome, direction, adds, partial exits, reversal boundaries, holding-time tertiles, fill-count tertiles, and all eligible accounts. Targets were approximately balanced for win/loss, Long/Short, and the two tertile dimensions while retaining rare edge cases.

| stratum | population | reviewed |
|---|---:|---:|
| adds | 55 | 15 |
| fills_few | 21 | 8 |
| fills_many | 20 | 5 |
| fills_medium | 20 | 7 |
| hold_long | 20 | 6 |
| hold_medium | 20 | 7 |
| hold_short | 21 | 7 |
| long | 34 | 10 |
| loss | 35 | 10 |
| no_adds | 6 | 5 |
| no_partial | 8 | 6 |
| no_reversal | 59 | 18 |
| partial | 53 | 14 |
| reversal | 2 | 2 |
| short | 27 | 10 |
| win | 26 | 10 |

## Reconciliation result

- Full-population automated boundary/metric reconciliation: 61/61 PASS
- PASS: 20/20
- FAIL: 0/20
- Reversal-boundary samples: 2
- Samples with non-zero builderFee: 3
- Tolerances: quantity 1e-8, price 1e-6, PnL/fee/Funding 1e-6.
- builderFee is checked as a component contained within fee and is not added again.
- Fill order is the original merged API order for equal timestamps, after stable timestamp ordering.

## Episode results

| episode | account | coin | fills | strata | result | difference |
|---|---|---|---:|---|---|---|
| A01-E001 | A01 | ADA | 146 | adds,fills_many,hold_short,no_reversal,partial,short,win | PASS | - |
| A02-E001 | A02 | FARTCOIN | 25 | adds,fills_medium,hold_long,no_partial,no_reversal,short,win | PASS | - |
| A02-E002 | A02 | TRUMP | 5 | adds,fills_few,hold_long,no_partial,no_reversal,short,win | PASS | - |
| A02-E003 | A02 | FARTCOIN | 20 | adds,fills_medium,hold_long,no_reversal,partial,short,win | PASS | - |
| A02-E004 | A02 | XPL | 23 | adds,fills_medium,hold_long,no_reversal,partial,short,win | PASS | - |
| A03-E001 | A03 | PUMP | 3 | adds,fills_few,hold_long,long,loss,no_partial,no_reversal | PASS | - |
| A03-E002 | A03 | CHIP | 31 | adds,fills_medium,hold_long,long,no_reversal,partial,win | PASS | - |
| A03-E003 | A03 | LIT | 74 | adds,fills_many,hold_medium,long,loss,no_reversal,partial | PASS | - |
| A04-E001 | A04 | HYPE | 187 | adds,fills_many,hold_short,long,loss,partial,reversal | PASS | - |
| A04-E002 | A04 | HYPE | 5 | fills_few,hold_short,loss,no_adds,partial,reversal,short | PASS | - |
| A04-E003 | A04 | HYPE | 39 | fills_medium,hold_short,loss,no_adds,no_reversal,partial,short | PASS | - |
| A05-E001 | A05 | HYPE | 12 | adds,fills_few,hold_medium,loss,no_reversal,partial,short | PASS | - |
| A06-E001 | A06 | SOL | 2 | fills_few,hold_short,no_adds,no_partial,no_reversal,short,win | PASS | - |
| A06-E002 | A06 | BTC | 2 | fills_few,hold_medium,loss,no_adds,no_partial,no_reversal,short | PASS | - |
| A06-E003 | A06 | HYPE | 6 | adds,fills_few,hold_medium,long,no_partial,no_reversal,win | PASS | - |
| A06-E004 | A06 | SOL | 5 | fills_few,hold_medium,long,loss,no_adds,no_reversal,partial | PASS | - |
| A07-E001 | A07 | xyz:CL | 63 | adds,fills_medium,hold_short,long,loss,no_reversal,partial | PASS | - |
| A08-E001 | A08 | ZEC | 490 | adds,fills_many,hold_medium,long,loss,no_reversal,partial | PASS | - |
| A09-E001 | A09 | VVV | 190 | adds,fills_many,hold_short,long,no_reversal,partial,win | PASS | - |
| A10-E001 | A10 | ETH | 20 | adds,fills_medium,hold_medium,long,no_reversal,partial,win | PASS | - |

## Quality gate

**PASS:** No material discrepancies were found in the reviewed sample or the full-population automated reconciliation. The project may proceed to the final TWAP/Funding/builder-fee accounting check.

The full anonymized raw-versus-reconstructed values and ordered fill traces are in `episode_review.csv`.

## Remaining limitations

- This review covers 20 of 61 eligible episodes, not the full population.
- The source cache is a fixed 30-day snapshot; this review does not prove completeness outside that window.
- Historical cross-margin state and liquidation distance remain unavailable and were not inferred.
