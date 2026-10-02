# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. 完了済みゲート

### episode再構成
- 全61episode 自動照合 61/61 PASS
- 層別20episode 匿名化レビュー 20/20 PASS
- 重大差異0

### 会計照合
- closedPnl / fee / Funding / net PnL 61/61 PASS
- builderFee二重計上0
- TWAP上限口座の除外条件をtestで固定
- 重大差異0

### 5分市場series coverage
- FEATURE_READY 0
- PARTIAL 24
- NOT_READY 37
- OHLCV / volume完備 24/61
- Funding availability 60/61
- historical mark / OI は0/61で unavailable
- entry足を除外した直前12本をpast-only契約としてtest済み

---

## 1. PARTIAL 24episodeへのpast-only特徴量付与【完了】

- price / volume / local structure: 24/24
- BTC relative: 24/24
- Funding rate: 23/24
- historical mark / OI: 0/24、NULL維持
- duplicate episode ID 0
- cached再実行で成果物byte-identical
- 26 tests PASS
- 成果物: `features/past-only-2026-10-02/`

以下は実装契約として保存する。

目的:
行動分類前に、entry時点で本当に利用可能だった市場情報だけから再現可能な特徴量基盤を作る。

対象:
PARTIAL 24episodeのみ。
NOT_READY 37episodeは対象外。

## 2. 実装するentry特徴量

最低限、以下を実装する。

### Price return
- return_5m
- return_15m
- return_1h

### Volume
- volume_ratio_5m
- volume_ratio_15m
- volume_zscore_1h（実装可能なら）

### Local structure
- distance_from_local_high
- distance_from_local_low
- range_position
- breakout_distance
- realized_volatility

### BTC relative
BTC側にも同じentry基準で必要窓が揃うepisodeのみ:
- btc_return_5m
- btc_return_15m
- btc_relative_strength_5m
- btc_relative_strength_15m

### Funding
- funding_rate
- entry以前の最新Fundingのみ
- 欠測1episodeはNULL維持

### OI / mark
今回はNULL維持。
historical seriesを推定・補間・0埋めしない。

---

## 3. 時点整合性

すべてのentry特徴量はentry時刻以前の確定データだけを使用する。

必須:
- entryを含む未確定5分足は使わない
- future candleを使わない
- episode exit情報を使わない
- MFE / MAE等のentry後データをentry特徴量へ混ぜない
- timezoneはUTC正規化

future leakage testを追加する。

---

## 4. 評価用post-entry特徴量は分離

entry後情報は別namespaceまたは別ファイルへ保存。

候補:
- evaluation_post_mfe
- evaluation_post_mae
- evaluation_post_max_adverse_move_time
- evaluation_post_max_favorable_move_time
- evaluation_post_volume_change

今回は実装してもよいが、entry分類ロジックから物理的・論理的に分離する。

---

## 5. 特徴量成果物

`features/past-only-2026-10-02/` を作る。

最低限:
- `README.md`
- `episode_features.csv`
- `feature_definitions.md`

episode_features.csvには最低限:
- episode_id
- coin
- side
- entry_time
- feature_availability
- 各past-only特徴量
- 欠測理由

feature_definitions.mdには各特徴量ごとに:
- 数式
- lookback
- 使用series
- timestamp基準
- 欠測処理
- BTC依存条件
- future leakage有無
を記録する。

---

## 6. 品質ゲート【PASS】

以下を満たしたら「行動分類開始可」とする。

- 24episode全件のfeature availabilityが明示
- 欠測0埋めなし
- OI/mark推定なし
- future leakage test PASS
- timestamp alignment test PASS
- 同一episodeで再実行時に同一結果
- 特徴量定義書完成

最低限のprice/volume特徴量が安全に付与できる24episode集合を確定した。

---

## 7. 次タスク: 行動ラベル定義の事前登録【最優先】

24episodeの値を見て閾値を都合よく調整しないよう、分類実行前に以下を文書化する。

- FOMO / Late Long・Short / ナンピン / Revenge候補の数式と閾値
- 必要seriesとfeature availability
- episode内イベント順序の条件
- 除外条件と重複ラベル方針
- Long/Shortの方向整合
- 対照群、評価指標、最低サンプル数
- exploratory PoCとconfirmatory拡大標本の分離

24episodeへの初回適用は実装・coverage確認に限定する。PnL差、勝率、逆指標性について結論を出さない。

## 8. 引き続き開始しない分類

今回はまだ以下を判定しない。

- FOMO
- Late Long / Short
- ナンピン
- Revenge
- Trapped
- Crowding
- Liquidation behavior
- 「養分は逆指標」等の結論

- Crowding: historical OI不足
- Trapped / Liquidation behavior: 過去margin・liquidation state不足
- 「養分は逆指標」等の結論: 標本不足

---

## 作業終了時

- `CURRENT_STATUS.md` 更新
- `NEXT_TASK.md` 更新
- 必要なら `DECISIONS.md` 追記
- テスト実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discordへ完了通知

養分ホイホイには変更を加えない。
