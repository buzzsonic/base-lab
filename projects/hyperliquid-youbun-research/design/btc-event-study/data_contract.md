# BTC event-study data contract — PHASE 0

更新: 2026-10-04 JST  
状態: PHASE 0 draft complete / collector未変更

## 目的

BTCのmarket windowごとに、固定100 walletの集団行動とBTC市場状態を同じ時刻軸で保存する。過去に復元できない口座stateを推定せず、forward snapshotとして新規収集する項目を明示する。

取得可否の正本は `field_matrix.csv` とする。

## 取得可否の意味

- `取得可能`: 公式APIの時刻付き履歴、または公式archiveから過去値を取得できる。ただし各endpointのretention、件数上限、archive欠測はcoverageとして保存する。
- `forwardなら取得可能`: 現在値またはstream eventは取得できるが、任意の過去時点を完全復元できない。collector開始後の観測値だけを使う。
- `取得不能`: 公式公開データから直接観測できない。推定値で置換しない。

## 結論

### 養分群

過去履歴として採用できる正本は `userFillsByTime`、`userTwapSliceFillsByTime`、`userFunding`。fillの `startPosition`、`side`、`sz`、`px`、`closedPnl` からadd/reduce/closeとrealized-loss exitを再構成できる。ただしfill/TWAPは保持件数上限があるため、既存historical pilotは母集団分析へ再利用しない。

current position、entry price、configured leverage、margin mode、liquidation price、account equity、margin usageは `clearinghouseState` の観測時点snapshotとして保存する。これらを過去fillから逆算しない。effective leverageはsnapshot内のposition notionalとaccount valueから派生させ、分母不足・非正値ではNULLにする。

明示的なliquidationは `userEvents` のliquidation event、またはfillの `liquidation` objectがある場合だけ認定する。通常の大幅損失closeをliquidationへ読み替えない。

### BTC市場

1m/5m OHLCVは `candleSnapshot` とcandle streamで取得する。直近5,000本制限を超えるAPI過去区間は欠測とする。mark、Funding、OIは `metaAndAssetCtxs` / `activeAssetCtx` をforward保存する。公式S3のasset contextは補助的な過去sourceだが、月次程度の遅延と欠測可能性があるため、forward collectorの代替正本にはしない。

aggressive buy/sell flowとlarge trade flowはBTC `trades` streamのside・price・sizeから作る。large閾値はPHASE 1で事前定義し、結果を見て遡及変更しない。order-book imbalanceは `l2Book` のprice/sizeを受信時刻つきで保存して計算する。BBOだけでは深さimbalanceを作らない。

公開市場全体の完全な「清算フロー」は公式APIで直接提供されない。観測対象walletの明示的liquidation event/fillはforward取得できるが、市場全体については `liquidation flow` を取得不能とする。将来別の公開一次sourceを追加する場合は、sourceとcoverageを別契約で追加する。

## 推奨sourceと保存grain

| dataset | source | grain | 推奨取得 | 用途 |
|---|---|---|---|---|
| wallet fills | REST `userFillsByTime` + TWAP endpoint | wallet × fill | 5分以下、overlap付き | new entry/add/reduce/close、realized loss |
| wallet funding | REST `userFunding` | wallet × funding event | 60分以下、overlap付き | cash flow、position size観測 |
| wallet state | REST/WS `clearinghouseState` | wallet × snapshot × position | 1分候補 | position、entry、leverage、liquidation distance、margin |
| wallet liquidation | WS `userEvents` + fills | wallet × event | continuous | 明示的liquidation証拠 |
| BTC candle | WS candle + REST recovery | BTC × 1m candle | continuous | price、volume、volatility |
| BTC asset context | WS `activeAssetCtx` | BTC × update | continuous | mark、OI、Funding |
| BTC trades | WS `trades` | BTC × trade | continuous | aggressive/large flow |
| BTC book | WS `l2Book` | BTC × snapshot | continuous、必要なら間引き | depth imbalance |

固定100 walletの同条件観測では、user-specific WebSocketの接続制約に依存しないようwallet stateの正本をREST snapshotとし、WS user eventは補助証拠として扱う。RESTとWSが競合した場合は双方をraw保存し、後段canonical化で不一致を明示する。

## 時刻・欠測契約

- rawには必ず `source_event_time_ms`、`received_at_ms`、`collector_run_id`、`source` を保存する。
- 同一windowへの割当はevent timeを使い、受信時刻は遅延監査に使う。
- wallet snapshotは観測時点のstateであり、次snapshotまで前方補完しない。
- interval集計は必要coverageを満たさない場合、0ではなくNULL/UNAVAILABLEにする。
- WebSocket reconnect区間、REST failure、page cap、retention risk、archive欠測を別々のquality flagで保持する。
- future featureとpost-event outcomeは別table/namespaceに置く。window終了後に確定する値をentry-side featureへ混ぜない。

## 最小coverage gate案（PHASE 1で確定）

- wallet fills/TWAP: endpoint failure 0、cap/retention risk 0、canonical continuity error 0。
- wallet state: window内snapshot coverage率と最大gapを記録。coverage不足windowはleverage/liquidation-distance分析から除外。
- BTC candle/asset context: required windowに欠損0。
- BTC trades/book: reconnect gapと最大silenceを記録。gapを跨ぐflow/imbalanceはUNAVAILABLE。
- liquidation: 明示的event/fillのみTRUE。観測経路不足はFALSEではなくUNAVAILABLE。

## PHASE 1へ渡す未確定事項

1. event windowを1分と5分のどちらをprimaryにするか。
2. wallet stateの取得周期と100 wallet完走時間。
3. L2 raw全量保存か、固定深度snapshot/集計併用か。
4. large tradeの事前登録閾値（notional固定、rolling percentile、または併記）。
5. accountValueが0以下・unified/portfolio margin口座のeffective leverage定義。

## 公式仕様

- Info endpoint: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- Perpetuals info: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- WebSocket subscriptions: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- Historical data: https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- Rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits

