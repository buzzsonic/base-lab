# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. 完結61episodeの層別目視検証（完了）

結果:
- 全61episode 自動照合 61/61 PASS
- 層別20episode 匿名化レビュー 20/20 PASS
- 重大差異0
- 10口座すべてをレビュー対象に含む
- 反転境界2/2確認
- 再構成ロジック修正なし

成果物:
- `reviews/episode-quality-2026-10-02/README.md`
- `reviews/episode-quality-2026-10-02/episode_review.csv`

この品質ゲートは通過済み。

---

## 1. TWAP / Funding / builder fee 会計照合【最優先】

目的:
episode純損益と費用の二重計上・欠落を防ぎ、行動分析前の会計品質ゲートを確定する。

### 対象
eligible 10口座・完結61episode。

### 確認項目
全61episodeについて以下を集計・照合する。

- closedPnl
- fee
- builderFee
- Funding
- episode net PnL
- Funding発生episode数
- Funding総額
- builderFee非zero episode数
- builderFeeがfeeへ含まれているか
- feeへのbuilderFee再加算が起きていないか
- TWAP関連fillの有無
- TWAP上限口座が確実に分析対象外になっているか

### TWAP
- eligible 10口座でTWAP追加0件であることを再確認。
- TWAP endpoint 2,000件上限に達した口座は引き続き除外。
- その除外条件をfixture / test / reportに残す。
- 将来TWAP fillがある場合のdata contractも明記する。

### 成果物
`reviews/accounting-quality-2026-10-02/` を作り、最低限以下を保存。

- `README.md`
- episode単位reconciliation CSV
- Funding集計
- builderFee集計
- TWAP除外条件
- PASS / WARN / FAIL判定

### 品質ゲート
- 二重計上0
- 欠落0、または既知欠測として説明可能
- builderFee包含関係が確定
- TWAP除外条件がtestで担保
- 重大差異0

重大差異があれば修正・再テスト・再照合してから次へ進む。

---

## 2. 5分市場系列coverage定量化【会計ゲートPASS後】

目的:
FOMO / Late / Trapped等の判定に必要な市場特徴量を、どのepisodeで安全に計算できるか確定する。

### episodeごとに確認
entry前後の必要時間窓について、以下の取得可否とcoverage率を保存する。

- OHLCV
- mark price
- OI
- Funding
- 可能なら trades / volume

### 原則
- 欠測は0で埋めない。NULL / unavailableとして扱う。
- future情報をentry時点特徴量へ混入させない。
- candle 5,000本制限により不足するepisodeは明示する。
- coverage不足episodeは行動分類対象から外すか、特徴量ごとに利用可否を持たせる。

### 成果物
`reviews/market-coverage-2026-10-02/` を作成。

最低限:
- episode ID
- coin
- entry time
- 必要窓
- OHLCV coverage
- OI coverage
- Funding coverage
- mark coverage
- 欠測理由
- FEATURE_READY / PARTIAL / NOT_READY

### 完了条件
- 61episode全件のcoverage状態が明示されている
- 欠測が0埋めされていない
- past-only条件をtestで担保
- 行動分類へ使えるepisode集合が確定する

---

## 3. 市場特徴量付与【coverage確認後】

FEATURE_READY episodeのみにpast-only特徴量を付与する。

候補:
- entry前5m / 15m / 1h return
- volume ratio
- OI change
- Funding
- BTC relative strength
- breakout distance
- local high / low distance
- volatility
- entry後のMFE / MAEは評価用として分離し、entry判定特徴量に混ぜない

特徴量定義・時点整合性・欠測処理を文書化する。

---

## 4. 行動分類はまだ開始しない

以下は今回まだ判定・結論化しない。

- FOMO
- Late Long / Short
- ナンピン
- Revenge
- Trapped
- Crowding
- 「養分は逆指標」等の結論

会計照合・市場coverage・past-only特徴量基盤が完成してから開始する。

---

## 作業終了時

- `CURRENT_STATUS.md` 更新
- `NEXT_TASK.md` 更新
- 必要なら `DECISIONS.md` 追記
- テスト実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discordへ完了通知

養分ホイホイには変更を加えない。
