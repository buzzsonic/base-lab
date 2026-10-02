# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. 完了済みゲート

### episode再構成
- 全61episode 自動照合 61/61 PASS
- 層別20episode 匿名化レビュー 20/20 PASS
- 重大差異0

### 会計照合
- closedPnl / fee / Funding / net PnL 61/61 PASS
- Funding非zero 44episode
- builderFee非zero 9episode
- builderFee二重計上0
- TWAP上限口座の除外条件をtestで固定
- 重大差異0

---

## 1. 5分市場系列coverage定量化【完了】

- 61episode全件を確定
- FEATURE_READY 0 / PARTIAL 24 / NOT_READY 37
- OHLCV・volume完備 24/61
- Funding availability 60/61
- historical mark・OIは0/61でNULL/unavailable
- entry足を除外した直前12本のpast-only契約、future leakage、UTC alignmentをtest化
- 成果物: `reviews/market-coverage-2026-10-02/`

以下は実施時に用いた契約として保存する。

目的:
FOMO / Late / Trapped / breakout / crowding等の行動分類に必要な市場特徴量を、どのepisodeで安全に計算できるか確定する。

対象:
eligible 10口座・完結61episode。

### episodeごとの必要窓

entry時点を基準に、少なくとも以下を確認する。

- entry前 60分
- entry前 15分
- entry前 5分
- entry後 60分（MFE/MAE等の評価用。entry判定特徴量には使わない）

### series

各episodeについて以下を確認する。

- 5m OHLCV
- mark price
- OI
- Funding
- volume / trades（取得可能なら）

### coverage保存項目

episode単位で最低限以下を保存する。

- episode_id
- wallet匿名ID
- coin
- side
- entry_time
- exit_time
- required_start
- required_end
- ohlcv_coverage_ratio
- mark_coverage_ratio
- oi_coverage_ratio
- funding_coverage_ratio
- volume_coverage_ratio（取得時）
- missing_series
- missing_reason
- FEATURE_READY / PARTIAL / NOT_READY

### 判定基準

FEATURE_READY:
- entry前に必要な主要seriesが揃う
- past-only特徴量を安全に算出可能
- 未来情報混入なし

PARTIAL:
- 一部series欠測
- 使用可能特徴量を個別管理できる

NOT_READY:
- entry前windowが不足
- candle上限等で主要特徴量を安全に作れない

### 原則

- 欠測を0で埋めない
- unavailable / NULLとして明示
- future情報をentry特徴量へ混入させない
- entry後データは評価用特徴量として別namespace / 別列群に分離
- candle 5,000本制限による欠測理由を明示
- coin/timezone/time alignmentをtestで担保

### 成果物

`reviews/market-coverage-2026-10-02/`

最低限:
- `README.md`
- `episode_market_coverage.csv`
- series別coverage集計
- FEATURE_READY / PARTIAL / NOT_READY件数
- coin別・期間別の欠測理由
- 行動分類へ進めるepisode集合

### 完了条件

- 61episode全件のcoverage状態が確定
- 欠測0埋めなし
- future leakage test PASS
- timestamp alignment test PASS
- FEATURE_READY集合が明示
- PARTIALを使う場合の許容特徴量が明示
- NOT_READY除外理由が明示

---

## 2. PARTIAL集合へのpast-only市場特徴量付与【最優先】

FEATURE_READYは0件のため、PARTIAL 24episodeだけを対象に、許可済みseriesから作れる特徴量を実装する。NOT_READY 37episodeは対象外。

### entry時点特徴量

最低限候補:

- return_5m
- return_15m
- return_1h
- volume_ratio_5m
- volume_ratio_15m
- oi_change_5m（今回はNULL。historical OI取得後のみ）
- oi_change_15m（今回はNULL。historical OI取得後のみ）
- funding_rate（LIT 1件はNULL。取得時点のpast-only確認必須）
- btc_return_5m
- btc_return_15m
- btc_relative_strength
- distance_from_local_high
- distance_from_local_low
- realized_volatility
- breakout_distance
- range_position

### 評価用特徴量

entry後情報は必ず別扱い。

- MFE
- MAE
- max_adverse_move_time
- max_favorable_move_time
- post_entry_volume
- post_entry_oi_change

これらをentry分類ロジックへ混入させない。

### 特徴量定義書

各特徴量について記録する。

- 数式
- 使用series
- lookback
- timestamp基準
- 欠測時処理
- future leakage有無
- 適用可能episode

### 今回の許容範囲

- 実値を許可: return_5m / return_15m / return_1h / volume系 / local high-low / realized volatility / breakout / range position
- NULL維持: mark依存 / OI依存 / 欠測Funding
- BTC相対系列はBTC側にも同一entry時点の直前12本が揃うepisodeだけ
- entry後評価列は別ファイルまたは`evaluation_post_*` namespace
- 24episodeすべてについて特徴量availabilityを保存する

---

## 3. 行動分類開始前ゲート

以下を満たしたら次回から行動分類開始可。

- episode品質 PASS
- 会計品質 PASS
- market coverage確定
- past-only特徴量生成 PASS
- future leakage test PASS
- FEATURE_READY集合確定

---

## 4. まだ開始しない分類

今回はまだ以下を判定しない。

- FOMO
- Late Long / Short
- ナンピン
- Revenge
- Trapped
- Crowding
- Liquidation behavior
- 「養分は逆指標」等の結論

---

## 作業終了時

- `CURRENT_STATUS.md` 更新
- `NEXT_TASK.md` 更新
- 必要なら `DECISIONS.md` 追記
- テスト実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discordへ完了通知

養分ホイホイには変更を加えない。
