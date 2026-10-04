# BTC market-event schema — PHASE 1

更新: 2026-10-04 JST  
schema version: `btc-market-event-v0.1.0`  
status: preregistered before report mock / forward collection

## 1. Unit of analysis

一次保存はUTC epochに整列した1分bucket、主分析は連続する5分windowとする。

- 1分raw bucket: `[minute_start_ms, minute_end_ms)`
- 5分event window: `[window_start_ms, cutoff_ms)`
- `cutoff_ms = window_start_ms + 5 minutes`
- post-event outcomeは常に`cutoff_ms`より後。event tableにpost-event price、PnL、MFE/MAEを置かない。
- 全5分windowを生成し、crowd eventの閾値選択はexploratory splitで後から行う。eventが無いwindowも対照候補として保持する。

UTC境界を使い、JSTは表示時だけ変換する。source event timeでwindowへ割り当て、received timeは遅延・gap監査専用とする。

## 2. Required identities and provenance

各rowの候補keyは `(schema_version, sample_version, cutoff_ms)`。

| field | type | definition |
|---|---|---|
| schema_version | string | 固定値`btc-market-event-v0.1.0` |
| sample_version | string | 検証済みHoihoi handoffのsample version |
| selection_version | string | 許可したoutcome-blind selection version |
| cutoff_ms | int64 | 5分windowの右端、futureとの境界 |
| window_start_ms | int64 | `cutoff_ms - 300000` |
| generated_at_ms | int64 | 集計生成時刻。feature計算には不使用 |
| wallet_source_sha256 | string | 受入済みhandoff file hash |
| raw_manifest_sha256 | string | このwindowが参照したraw manifest hash |

Hoihoi handoffはschema、hash、version、wallet重複、episode重複、quality gateを検証後にのみ受け入れる。handoffに含まれないwalletを同じsample versionへ追加しない。

## 3. Canonical wallet transitions

通常fillとTWAP sliceをdedupし、同一timestampは`startPosition -> afterPosition`鎖で整列する。flipはclose部分と反対sideのnew-entry部分へ数量分割する。

各fill transitionを以下へ一意に分類する。

- `NEW_LONG`: flatからLONG、またはSHORT flipのLONG新規部分
- `NEW_SHORT`: flatからSHORT、またはLONG flipのSHORT新規部分
- `ADD_LONG` / `ADD_SHORT`: 同方向positionの絶対数量増加
- `REDUCE_LONG` / `REDUCE_SHORT`: 同方向positionの絶対数量減少（flat到達を除く）
- `CLOSE_LONG` / `CLOSE_SHORT`: positionがflatへ到達する部分

continuity error、quantity mismatch、cap、retention risk、unresolved gapが1つでもあるwallet-windowはwallet集計から除外せず、window全体の`wallet_flow_status=UNAVAILABLE`とする。欠測walletを分母から黙って落とさない。

## 4. Wallet crowd fields

notionalは各transitionの`abs(price * transition_size)`。flipは分割後数量を使う。

| field | type | definition / missing rule |
|---|---|---|
| eligible_wallets | int | sample versionに含まれるwallet総数 |
| active_youbun_wallets | int/null | window内にBTC transitionがあるdistinct wallet |
| new_long_wallets | int/null | `NEW_LONG`があるdistinct wallet |
| new_short_wallets | int/null | `NEW_SHORT`があるdistinct wallet |
| long_notional_usd | decimal/null | `NEW_LONG + ADD_LONG` notional合計 |
| short_notional_usd | decimal/null | `NEW_SHORT + ADD_SHORT` notional合計 |
| long_short_imbalance | decimal/null | `(long_notional-short_notional)/(long_notional+short_notional)`。分母0はNULL |
| new_entry_long_notional_usd | decimal/null | `NEW_LONG`部分だけのnotional |
| new_entry_short_notional_usd | decimal/null | `NEW_SHORT`部分だけのnotional |
| add_long_wallets / add_short_wallets | int/null | side別ADDのdistinct wallet |
| averaging_down_wallets | int/null | adverse add条件を満たすdistinct wallet |
| pyramiding_wallets | int/null | favorable add条件を満たすdistinct wallet |
| exit_wallets | int/null | REDUCEまたはCLOSEがあるdistinct wallet |
| realized_loss_exit_wallets | int/null | REDUCE/CLOSEかつ`closedPnl < 0`のdistinct wallet |
| realized_loss_exit_notional_usd | decimal/null | 上記transition notional合計 |
| explicit_liquidation_wallets | int/null | 明示的liquidation event/fillのdistinct wallet |

averaging down / pyramidingは既存preregistered-v1のside対称条件を使う。add sizeが直前position絶対量の5%以上かつ、直前平均建値から5bp以上adverse/favorableであること。必要なpre-add stateが欠ければ当該wallet判定は`UNAVAILABLE`であり0件に含めない。

## 5. Entry price fields

entry集合は`NEW_LONG` / `NEW_SHORT`の新規部分だけ。ADDをentry価格集中へ混ぜない。

| field | definition |
|---|---|
| entry_price_vwap | 全new-entry notional / 全new-entry size |
| entry_price_wallet_median | wallet別initial-entry VWAPの中央値 |
| entry_price_iqr_bps | wallet別initial-entry VWAPのIQRをmedian比bps化 |
| entry_price_concentration_25bps | wallet medianの±25bp内にあるnew-entry notional / 全new-entry notional |
| entry_distance_from_prior_60m_high_bps | `(entry_price_vwap / prior_60m_high - 1) * 10000` |
| entry_distance_from_prior_60m_low_bps | `(entry_price_vwap / prior_60m_low - 1) * 10000` |

new entryが無いwindowは全entry fieldをNULLにする。prior high/lowは`[cutoff_ms-60m, cutoff_ms)`の確定1分足60本から作り、1本でも欠ければdistanceをNULLにする。

## 6. Forward wallet-state fields

各walletについて`cutoff_ms`以前で最も新しいsnapshotを使う。ageが120秒超ならstaleとして統計から外すが、walletを0 leverageとして扱わない。

| field | definition |
|---|---|
| wallet_state_observed | non-stale snapshotを持つwallet数 |
| wallet_state_coverage | `wallet_state_observed / eligible_wallets` |
| leverage_median / leverage_p90 | configured leverage value。coverage 80%未満はNULL |
| effective_leverage_median / p90 | `abs(positionValue)/applicable accountValue`。分母非正値・mode不明を除外しcoverage併記 |
| liquidation_distance_bps_median / p10 | LONGは`(mark-liquidationPx)/mark`、SHORTは`(liquidationPx-mark)/mark`をbps化。null/non-positiveは除外 |
| margin_usage_ratio_median / p90 | applicable totalMarginUsed / accountValue。分母非正値は除外 |

分布値は有効coverage 80%以上のときだけ生成する。`wallet_state_coverage`自体は常に保存する。

## 7. BTC market fields

すべて`cutoff_ms`までに観測済みの値だけを使う。

| field | definition |
|---|---|
| btc_open / high / low / close | window内の確定1分足5本から集約 |
| btc_return_5m | `close/open - 1` |
| btc_return_prior_15m / 60m | cutoff以前の確定1分足から計算 |
| btc_volume_5m | 5本のbase volume合計 |
| btc_volume_ratio_prior_60m | 直近5分volume / その前55分を5分換算した平均。分母0はNULL |
| btc_realized_vol_prior_60m | 1分log returnの標本標準偏差 × `sqrt(60)` |
| btc_prior_60m_high / low | cutoff以前60本のhigh最大 / low最小 |
| btc_high_break_failed | window highが直前55分highを上抜いたがcloseが同high以下ならTRUE |
| btc_low_break_failed | window lowが直前55分lowを下抜いたがcloseが同low以上ならTRUE |
| btc_oi_start / end | window両端に最も近いnon-stale asset ctx OI |
| btc_oi_change_pct | `oi_end/oi_start - 1`。分母0はNULL |
| btc_funding_rate | cutoff以前の最新asset ctx funding |
| aggressive_buy_notional / sell_notional | BTC trades side別`px*sz`合計 |
| aggressive_flow_imbalance | `(buy-sell)/(buy+sell)`。分母0はNULL |
| large_buy_notional / large_sell_notional | notionalが過去60分のBTC trade notional p99以上のtrade合計 |
| opposite_large_flow_notional | crowd imbalanceと逆方向のlarge notional。crowd imbalance NULL/0ならNULL |
| l2_imbalance_5 | 各snapshotのtop-5 bid/ask size imbalance中央値 |
| bbo_spread_bps | `(ask-bid)/mid*10000`のwindow中央値 |

large trade閾値は各window開始前60分のtradeだけから計算する。60分coverage不足またはtrade数100未満ならlarge flow fieldsはNULLにする。

## 8. Coverage and status fields

| field | allowed values / definition |
|---|---|
| wallet_flow_status | `READY / UNAVAILABLE` |
| wallet_state_status | `READY / PARTIAL / UNAVAILABLE` |
| btc_candle_status | `READY / UNAVAILABLE` |
| btc_asset_ctx_status | `READY / UNAVAILABLE` |
| btc_trade_status | `READY / UNAVAILABLE` |
| btc_book_status | `READY / UNAVAILABLE` |
| unresolved_gap_count | source別gap合計 |
| max_received_lag_ms | event timeからreceived timeまでの最大遅延 |
| feature_ready | required core: wallet flow + BTC candle + BTC asset ctxが全てREADY |

Core event rowはwallet flow、BTC candle、BTC asset contextがREADYの場合だけ`feature_ready=true`。trade/book/stateはoptional feature groupであり、不足時にcore rowを捨てず該当列をNULLにする。

## 9. Leakage boundary and forbidden fields

event tableへ以下を保存してはならない。

- `cutoff_ms`後のprice/return/high/low
- future MFE/MAE
- future exit、future realized PnL、future liquidation
- outcome label、勝敗、profit factor
- full-sample percentileまたはheld-out期間から計算した閾値

集計関数は`cutoff_ms`以降のrowを入力として受け取らない。outcome tableとのjoinはレポート・分析層だけで行う。

## 10. Handoff compatibility

入力sampleの最低許可schemaは`hoihoi-btc-handoff-v0.1`。Hoihoiのepisode referenceはwallet sampleの品質・時刻照合に使うが、handoffのbehavior profileをevent発火条件の必須要件にしない。profileでsampleを再抽出すると特定行動の過剰抽出になるためである。

