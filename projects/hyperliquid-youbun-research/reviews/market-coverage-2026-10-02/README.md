# Market coverage review — 2026-10-02

## Result

All 61 eligible completed episodes have an explicit coverage state: FEATURE_READY 0, PARTIAL 24, NOT_READY 37.

This is a coverage audit, not a behavior classification. FOMO, Late, averaging down, Revenge, Trapped, Crowding, and liquidation labels were not computed.

| state | episodes | interpretation |
|---|---:|---|
| FEATURE_READY | 0 | Complete past-only OHLCV, volume, mark, OI, and Funding |
| PARTIAL | 24 | Complete past-only candles; only price-return/volume features are allowed |
| NOT_READY | 37 | Entry lookback candle window is incomplete; excluded from market-feature analysis |

## Window contract

- Entry features use exactly 12 completed 5-minute bars ending at the floor of entry time. The candle containing entry is excluded.
- Entry-minus-5m, 15m, and 60m are nested inside that past-only window.
- The 12 bars after the entry boundary are stored only under `evaluation_post_*`; they never affect entry availability.
- Funding is available only when the latest observation at or before entry is no more than two hours old.
- Missing values are empty/NULL, never numeric zero. In particular historical mark and OI remain unavailable.

## Source limits

- Official candle/Funding requests returned at least one candle for 15/25 episode coins.
- The Info API exposes current mark/OI through `metaAndAssetCtxs`, not a historical time-range endpoint.
- The official archive can contain `asset_ctxs`, but it is uploaded approximately monthly, may be delayed, and may have missing data. No verified archive rows for this PoC interval were available in the project cache, so mark/OI were not inferred.
- The candle endpoint exposes only the most recent 5,000 candles. Old episodes outside that range remain NOT_READY.

Official references:
- https://hyperliquid.gitbook.io/Hyperliquid-docs/for-developers/api/info-endpoint
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data

## Artifacts

- `episode_market_coverage.csv`: all episode-level windows, ratios, NULLs, reasons, and states
- `series_coverage_summary.csv`: complete/unavailable/incomplete counts by series
- `coin_source_coverage.csv`: requested interval and returned row counts by coin

## Gate decision

The market-coverage inventory is complete, but the full market-feature gate is not. FEATURE_READY is zero while historical mark/OI are unavailable. PARTIAL episodes may be used only for explicitly named price-return and volume features; they must not silently enter OI/crowding/mark-dependent analyses.
