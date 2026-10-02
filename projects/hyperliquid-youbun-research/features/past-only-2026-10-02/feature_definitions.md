# Past-only feature definitions

All entry features use exactly 12 completed 5-minute candles in `[floor5m(entry)-60m, floor5m(entry))`. The candle containing entry and all later candles are excluded. Prices and volumes come from the official `candleSnapshot`; Funding comes from the latest official `fundingHistory` observation at or before entry, no more than two hours old.

| feature | formula and lookback | missing rule | leakage |
|---|---|---|---|
| return_5m | last candle close / last candle open - 1 | NULL unless all 12 source bars exist | past-only |
| return_15m | last close / open three bars earlier - 1 | same | past-only |
| return_1h | last close / first open in 12-bar window - 1 | same | past-only |
| volume_ratio_5m | last-bar volume / mean volume of prior 11 bars | NULL when prior mean is zero | past-only |
| volume_ratio_15m | sum of last 3 bars / prior 9-bar mean scaled to 3 bars | NULL when prior equivalent is zero | past-only |
| volume_zscore_1h | z-score of last-bar volume against prior 11 bars, population SD | NULL when prior SD is zero | past-only |
| distance_from_local_high | last close / maximum high over 12 bars - 1 | NULL when denominator is zero | past-only |
| distance_from_local_low | last close / minimum low over 12 bars - 1 | NULL when denominator is zero | past-only |
| range_position | (last close - 12-bar low) / (12-bar high - low) | NULL for zero-width range | past-only |
| breakout_distance | LONG: last close / prior-11-bar high - 1; SHORT: prior-11-bar low / last close - 1 | NULL when denominator is zero | past-only; side-adjusted |
| realized_volatility | sample SD of 11 consecutive 5-minute log close returns | NULL for non-positive price or fewer than two returns | past-only; not annualized |
| btc_return_5m / 15m | same return definitions on BTC at the identical entry boundary | NULL unless BTC has all identical 12 timestamps | past-only |
| btc_relative_strength_5m / 15m | episode-coin return minus BTC return | NULL when BTC return is NULL | past-only |
| funding_rate | latest Funding rate with timestamp <= entry and lag <= 2h | NULL otherwise | past-only |
| mark_price / oi | not computed in this PoC | always NULL until verified historical series exists | unavailable |

No exit time, PnL, MFE, MAE, or post-entry candle participates in this file. Post-entry evaluation features are intentionally not produced in this task.
