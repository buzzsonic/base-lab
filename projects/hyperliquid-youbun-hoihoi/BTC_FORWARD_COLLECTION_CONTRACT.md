# BTC research forward collection contract v1

## 状態

`DESIGNED_NOT_STARTED`。既存current/shadow checkpointは変更しない。定期workflowはまだ有効化しない。

## 目的

BTC research sample v0.1に必要な通常fillsとTWAP slicesを、同一timestampのsource orderを壊さずforward収集する。公開・読み取り専用APIだけを使用し、注文・署名・秘密鍵・市場反応分析は行わない。

## Namespace

```text
projects/hyperliquid-youbun-hoihoi/outputs/btc-research-forward-v1/
  state/collector_state.json
  raw/date=YYYY-MM-DD/run=YYYYMMDDTHHMMSSZ/
    fills.jsonl
    twap.jsonl
    manifest.json
  canonical/
    wallets/<wallet>/btc_fills.parquet
    wallets/<wallet>/quality.json
```

既存`outputs/current/`、`outputs/cohorts/stratified-20261003/`、research sampleを上書きしない。

## Source

| source | API type | cadence | page limit assumption |
|---|---|---:|---:|
| regular fills | `userFillsByTime`、`aggregateByTime=false` | 20分 | 2,000 |
| TWAP slices | `userTwapSliceFillsByTime` | 20分 | 500 |

初回成功時の`analysis_start_ms`を固定し、それ以前を研究windowへ混ぜない。各pollは前回成功時点から20分overlapする。timestamp境界はinclusiveで再取得し、`+1ms`で飛ばさない。

## Source-order envelope

raw rowには必ず以下を持たせる。

- `schema_version`, `collector_version`, `run_id`
- `wallet`, `source_endpoint`, `source_time_ms`
- `page_index`, `row_index`, `source_sequence`
- `response_received_at`, `dedup_key`, `payload`

`row_index`はAPI response配列内の位置、`source_sequence`はrun×wallet×endpoint内で単調増加する整数。同一timestampをhash・tid・priceでsortしてはならない。

rawはappend-only。overlap再取得による重複もrawへ残す。canonical viewだけで`source_endpoint + wallet + dedup_key`のfirst-seen rowを採用し、first-seenの`source_sequence`を保持する。

## Regular/TWAP merge

1. endpointごとのsource orderを保持する。
2. timestampが異なるrowは時刻順。
3. 同一timestampでendpointをまたぐrowは、直前timestampの確定positionを始点に、観測済み`startPosition -> afterPosition`が1本の鎖になる順序を探索する。
4. 有効な鎖が一意なら採用する。
5. 0本または複数なら`AMBIGUOUS_SAME_MS_ORDER`としてwallet/dayをUNAVAILABLEにする。推定sortは行わない。

## Fail-closed Gate

次のいずれかでcheckpointを進めず、handoff対象外とする。

- endpoint failure、pagination stall、page safety cap
- retention risk、未解消時間gap
- source sequence欠落・重複
- 同一ms mergeが一意に解けない
- continuity error、quantity mismatch
- TWAP endpoint未取得またはcap到達
- sample manifest/hashの予期しない変更

## Rollout

1. unit fixtureでsource order、overlap dedup、TWAP merge、曖昧時failを検証する。
2. timer無効の1-wallet canaryを1回実行し、rawだけをartifactへ保存する。
3. 同じwalletをoverlap付きで再実行し、canonical first-seen一致を確認する。
4. 少数walletで24時間観察する。
5. 100/200 walletへ広げる前に所要時間・API weight・欠測率を判定する。
6. 最低7成功JST日後にのみBTC sample v0.1を再dry-runする。

1,000-wallet拡大、sample自動昇格、養分くんへの自動採用は対象外。
