# BTC post-event outcome schema — PHASE 1

更新: 2026-10-04 JST  
schema version: `btc-post-event-outcome-v0.1.0`  
status: preregistered before report mock / forward collection

## 1. Physical separation

このtableはevent feature tableと別file・別namespaceで生成する。keyは `(schema_version, sample_version, cutoff_ms, horizon_min)`。`horizon_min`は`5, 15, 30, 60`のみ。

- anchor: eventの`cutoff_ms`で確定した直前1分足close
- outcome interval: `[cutoff_ms, cutoff_ms + horizon_min)`に属する確定1分足
- outcome生成時刻はhorizon終了後でなければならない
- outcome値をevent threshold、wallet選抜、feature percentileの計算へ戻さない

## 2. Price outcomes

| field | type | definition |
|---|---|---|
| anchor_price | decimal | event cutoff直前の確定1分足close |
| horizon_close | decimal/null | horizon最終確定1分足close |
| future_return | decimal/null | `horizon_close / anchor_price - 1` |
| future_up | bool/null | `future_return > 0` |
| future_down | bool/null | `future_return < 0` |
| future_flat | bool/null | `future_return == 0` |
| mfe_up | decimal/null | `max(high)/anchor_price - 1` |
| mae_down | decimal/null | `min(low)/anchor_price - 1`。通常0以下 |
| max_abs_move | decimal/null | `max(abs(mfe_up), abs(mae_down))` |
| time_to_high_sec | int/null | interval内最大highの最初の時刻−cutoff |
| time_to_low_sec | int/null | interval内最小lowの最初の時刻−cutoff |

必要な1分足がhorizon本数ちょうど揃わなければ、price outcome群を全てNULLにして`price_outcome_status=UNAVAILABLE`とする。

## 3. Crowd-aligned outcomes

event tableの`long_short_imbalance`の符号だけを使い、強さの閾値はPHASE 2 mock後のexploratory定義へ分離する。

| field | definition |
|---|---|
| crowd_side | imbalance > 0は`LONG`、< 0は`SHORT`、0/NULLはNULL |
| crowd_aligned_return | LONGならfuture_return、SHORTなら`-future_return` |
| opposite_return | `-crowd_aligned_return` |
| moved_against_crowd | `crowd_aligned_return < 0`。crowd_side NULLならNULL |
| crowd_aligned_mfe | LONGならmfe_up、SHORTなら`-mae_down` |
| crowd_aligned_mae | LONGならmae_down、SHORTなら`-mfe_up` |

これは「養分が逆指標」というlabelではない。連続値と単純方向を保存するだけで、条件付き確率の結論はvalidation/held-out後まで出さない。

## 4. Post-event market flow

| field | definition / missing rule |
|---|---|
| post_aggressive_buy_notional | horizon内BTC tradesのbuy notional |
| post_aggressive_sell_notional | horizon内BTC tradesのsell notional |
| post_aggressive_flow_imbalance | `(buy-sell)/(buy+sell)`。分母0はNULL |
| opposite_large_flow_occurred | event crowd sideと逆方向のlarge tradeが1件以上 |
| opposite_large_flow_notional | 逆方向large trade notional合計 |
| time_to_first_opposite_large_flow_sec | 最初の逆方向large trade時刻−cutoff |
| oi_change_pct | horizon末OI / cutoff OI - 1 |
| oi_drop_occurred | horizon内OIがcutoff比で低下した観測があるか |
| funding_end | horizon終了以前の最新Funding |

large trade閾値はevent cutoff以前60分だけから固定した値をoutcome側へ渡す。post-event tradeを含めて閾値を再計算しない。trade/asset ctx coverage不足なら各groupをNULLにする。

## 5. Observed wallet exits after event

対象は同じ受入済みwallet sampleのみ。

| field | definition |
|---|---|
| exit_wallets | horizon内にBTC REDUCE/CLOSEがあるdistinct wallet |
| realized_loss_exit_wallets | horizon内REDUCE/CLOSEかつclosedPnl<0のdistinct wallet |
| realized_loss_exit_notional_usd | 上記transition notional合計 |
| explicit_liquidation_wallets | horizon内に明示的liquidation evidenceがあるdistinct wallet |
| panic_exit_candidate_wallets | crowd sideと同方向positionをevent cutoffで持ち、逆行後にrealized-loss exitしたdistinct wallet |

`panic_exit_candidate`は観測sequence名であり心理状態の断定ではない。判定にはcutoff時position snapshot、horizon price path、exit fillの3系列すべてが必要。いずれか欠測ならNULL/UNAVAILABLEにする。

market-wide liquidation flowは保存しない。観測walletの`explicit_liquidation_wallets`を市場全体へ外挿しない。

## 6. Event-chain flags

以下は必要seriesが全てREADYの場合だけ評価する。

| field | definition |
|---|---|
| crowd_then_opposite_flow | crowd_sideあり、かつopposite large flow発生 |
| crowd_then_reversal | crowd_sideあり、かつmoved_against_crowd |
| crowd_flow_reversal | 上記2条件を満たし、opposite flowがcrowd側最大有利価格より前に発生 |
| crowd_flow_reversal_exit | `crowd_flow_reversal`後にpanic exit candidateまたは明示的liquidationが発生 |

条件不足はFALSEではなくNULL。event chainは「大口が狙った」証拠ではなく、観測可能な順序の一致だけを表す。

## 7. Coverage fields

| field | allowed values / definition |
|---|---|
| price_outcome_status | `READY / UNAVAILABLE` |
| trade_outcome_status | `READY / UNAVAILABLE` |
| asset_ctx_outcome_status | `READY / UNAVAILABLE` |
| wallet_exit_status | `READY / UNAVAILABLE` |
| event_chain_status | 全必要group READYなら`READY`、それ以外`UNAVAILABLE` |
| missing_reasons | controlled reason codeの配列 |
| max_received_lag_ms | horizon内最大受信遅延 |
| generated_at_ms | outcome生成時刻 |

controlled reason code初期集合:

- `MISSING_CANDLE`
- `TRADE_STREAM_GAP`
- `ASSET_CTX_GAP`
- `WALLET_FILL_GAP`
- `WALLET_STATE_STALE`
- `LIQUIDATION_EVENT_COVERAGE_GAP`
- `ANCHOR_UNAVAILABLE`

## 8. Overlap and statistical use

5分ごとのrowへ15/30/60分outcomeを付けるため、隣接rowのoutcomeは重複する。推論時は独立標本とみなさず、日単位block bootstrapまたは時系列HAC、wallet sample version単位のclusterを使用する。探索・validation・held-outは時系列順に分割し、同一event chainを期間境界へ重複配置しない。

PHASE 1では成績集計、閾値探索、p値計算を行わない。

## 9. Join contract

eventとoutcomeのjoin keyは`sample_version + cutoff_ms`。異なるsample versionを同じrowへ結合しない。eventの`feature_ready=false` rowはoutcomeがREADYでも主分析へ採用しないが、coverage監査用に保持する。

