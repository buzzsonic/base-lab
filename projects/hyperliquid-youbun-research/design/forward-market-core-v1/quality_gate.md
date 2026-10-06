# Forward market core v1 quality gate

## Gate A: implementation review

live canary前に全て必要。

- `market-core-v1`専用entrypoint、state、lock、service、timer、namespace
- wallet `forward-v3`のfile・state・runtimeへ変更なし
- fixtureだけでraw-before-checkpoint、restart重複、candle確定、REST修復、ctx staleをtest
- public read-only endpointだけ。注文・署名・秘密鍵なし
- raw payload、manifest、gap、healthを監査可能
- live起動は別タスクで明示承認する

## Gate B: 24時間canary

実装後も、まずBTC market coreだけを24時間観測する。仮説成績は計算しない。

- process crash / write error / parse error: 0
- 1分candle canonical: 期待1,440本の100%。REST修復本数を別表示
- unresolved candle gap: 0
- 5分cutoffに対するasset ctx fresh coverage: 99%以上
- 120秒を超えるasset ctx stale interval: 0
- restart/reconnect試験後もcanonical duplicate: 0
- source timestampが無いctx rowを受信時刻で偽装: 0

1つでも外れたらcanary FAIL。欠測を補完して合格にしない。

## Gate C: research-ready observation

24時間canary PASS後、連続7 JST日で評価する。

- 各JST日の1分candle canonical coverage: 100%（REST修復は明示）
- 全期間のasset ctx fresh coverage: 99.5%以上、各日99%以上
- unresolved candle gap: 0
- 120秒超asset ctx stale interval: 0
- health manifest欠落: 0
- event/outcome pipelineへ渡すwindowは、個別cutoffのcore coverageが完全なものだけ

Gate Cを通過してもconfirmatory backtestが自動解禁されるわけではない。まずexploratory splitだけでPHASE 4Bを再開する。

## Optional trades gate

tradesはcore Gateと分離する。H08を`READY`にする条件は、対象window内の連続coverage 99.5%以上、unresolved gap 0、dedup key衝突0。未達ならH08は`UNAVAILABLE`のままにする。

## 停止条件

- wallet collectorとのstate/lock/namespace共有
- gapの前方補完、0埋め、推定ctx
- source時刻の捏造
- liveデータをvalidation / held-outの閾値調整に使用
- collector開始だけをもって研究結果を有効化
