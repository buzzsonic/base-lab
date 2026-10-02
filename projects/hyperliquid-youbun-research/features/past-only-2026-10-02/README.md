# Past-only market features — 2026-10-02

## Result

The 24 PARTIAL episodes received deterministic price and volume features from the 12 completed 5-minute candles strictly before entry.

| check | result |
|---|---:|
| Input PARTIAL episodes | 24 |
| Price/volume feature rows | 24 |
| BTC-relative coverage | 24/24 |
| Funding-rate coverage | 23/24 |
| Rows with BTC and Funding available | 23/24 |
| Historical mark/OI coverage | 0/24 |
| Duplicate episode IDs | 0 |

Availability classes: {'PRICE_VOLUME_BTC': 1, 'PRICE_VOLUME_BTC_FUNDING': 23}.

## Gate decision

PASS for the limited price/volume feature contract. Every output row has the full 12-bar past-only source window, unavailable fields remain empty, and BTC/Funding dependencies are individually gated. This does not validate or create any behavioral label.

## Reproducibility and exclusions

- `episode_features.csv` contains only anonymized episode/account IDs; wallet addresses are absent.
- The entry candle, exit time, PnL, and all post-entry candles are physically absent from the calculation interface.
- Historical mark and OI are not inferred, interpolated, or zero-filled.
- The 37 NOT_READY episodes are not present in this feature table.
- Cached reruns must produce byte-identical CSV output.

## Artifacts

- `episode_features.csv`: 24 episode-level feature rows
- `feature_definitions.md`: formulas, lookbacks, source series, NULL rules, BTC conditions, and leakage status
