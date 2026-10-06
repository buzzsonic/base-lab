# BTC forward market core collector contract v1

## 目的と境界

historical dataで欠けているBTCのmark / OI / Fundingと1分candleを、観測開始後だけ保存する。H08向けpublic tradesはoptional groupに分離する。既存wallet collector、wallet state、BBO/L2、liquidation eventはこのcoreへ混ぜない。

この文書は設計のみを固定する。live collector、VPS service、timer、GitHub scheduleは作動させない。

## 分離契約

| 項目 | market core v1 |
|---|---|
| collector version | `market-core-v1` |
| 保存namespace | `forward-market-core-v1/` |
| 実装予定entrypoint | `scripts/forward_market_core_collect.py` |
| state / lock / service | wallet `forward-v3` と共有しない |
| 対象 | BTC market public dataだけ |

既存`forward-data-v3/`、wallet checkpoint、Docker runtime、systemd unitを変更または再利用しない。障害とcheckpointを相互伝播させない。

## Core streams

### `btc_asset_ctx`

- 正本: WebSocket `activeAssetCtx`、coin `BTC`
- raw: 受信payloadをappend-only保存
- 必須値: `markPx`、`openInterest`、`funding`
- 補助値: `oraclePx`、`midPx`、`dayNtlVlm`、`prevDayPx`
- WebSocket messageにsource timestampが無ければ`source_time_ms=null`とする。`received_at_ms`から取引所時刻を捏造しない。
- event featureではcutoff以前120秒以内の観測だけをfreshとする。無通信は値0ではなく`STALE`。
- 切断中のctxはREST candleから推定しない。公式archiveを将来使う場合も`AUXILIARY_ARCHIVE`として別保存し、黙って正本へ混ぜない。

### `btc_candle_1m`

- 正本: WebSocket `candle`、coin `BTC`、interval `1m`
- raw: 更新途中を含む全messageをappend-only保存
- canonical: close時刻を過ぎた確定足だけを、`(coin, interval, t)`で1行にupsertする
- 期待系列: `t`が60,000ms間隔で連続すること
- gap修復: REST `candleSnapshot`を、公式上限の直近5,000本内だけに使える
- 修復rowは`repair_source=REST_CANDLE_SNAPSHOT`、gapは`RESOLVED_REST`と明示する
- 上限外・取得失敗・値不一致は`UNRESOLVED`。前方補完や線形補間をしない

### `collector_health`

- process start/stop、connection open/close、subscribe ack、heartbeat、reconnect、parse/write errorを保存する
- heartbeatは30秒ごと。接続IDと接続内sequenceを持つ
- asset ctxはevent-drivenなので、沈黙だけから「何message欠けたか」は断定しない。120秒超を`STALE_INTERVAL`として記録する
- candleは期待時刻が既知なので、欠番を明示的gap intervalとして記録する

## Optional stream

### `btc_trades`

- 正本: WebSocket `trades`、coin `BTC`
- dedupは`tid`がある場合は`tid`、無い場合はpayloadのcanonical hash
- coreとは別checkpoint・別health groupにする
- trades障害でasset ctx/candle collectorを停止させない
- coverage不足時、opposite flow / large flowは`UNAVAILABLE`。0件と解釈しない

## 共通raw envelope

全raw rowは次を持つ。

`schema_version`, `collector_version`, `stream`, `source`, `coin`, `source_time_ms`, `received_at_ms`, `connection_id`, `sequence_in_connection`, `is_snapshot`, `repair_source`, `dedup_key`, `payload`

`source_time_ms`はnullable、`received_at_ms`は必須。rawをdurableに書き終える前にcheckpointを進めない。再起動時は重複を許容して再取得し、canonical viewでdedupする。

## Gapと欠測

| stream | gap検知 | 修復 | 分析上の扱い |
|---|---|---|---|
| asset ctx | disconnect / 120秒超stale | 自動修復しない | cutoffがfreshでなければcore event `NOT_READY` |
| 1m candle | 60秒sequence欠番 | 直近5,000本内のみREST | unresolvedを跨ぐfeature/outcomeは`UNAVAILABLE` |
| trades | disconnect / health gap | v1では自動修復しない | H08だけ`UNAVAILABLE`、coreは維持 |

## Transaction

1. raw payloadをappend-only runへ保存する。
2. manifestとrow countを確定する。
3. atomicにcheckpointを更新する。
4. error、disk write失敗、manifest不一致ではcheckpointを更新しない。

値の前方補完、gap区間の0埋め、ctxとcandleからのtrade flow推定は禁止する。

## 安全

Hyperliquid public read-only dataだけを使う。注文、署名、秘密鍵、API wallet、資金移動、Discord通知はcollectorに含めない。
