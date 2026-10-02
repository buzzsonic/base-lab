# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

# 運用方針

原則として2〜3工程を連続実行し、品質ゲートPASS後は次工程へ進む。重大差異・データ破損・future leakage・仕様衝突のみ停止する。終了時は状態文書、test、commit/push、Discord通知まで行う。養分ホイホイは変更しない。

# 完了済み

- episode再構成61/61、層別目視20/20、会計照合61/61 PASS
- 市場coverage確定、PARTIAL 24episodeへpast-only特徴量付与
- PHASE 1: 行動ラベルv1.0.0事前登録 PASS
- PHASE 2: 24episode outcome-free dry-run PASS
- PHASE 3: exploratory behavior distribution summary PASS
- v1閾値は凍結済み。変更はv2として作り、v1を上書きしない

成果物:
- `labels/preregistered-v1/`
- `analysis/exploratory-behavior-v1/`

# 次タスク: outcome-blind品質レビューと標本拡大設計

## 1. ラベル品質レビュー

- TRUE例を全件確認
- FALSE例はLong/Short・coin・walletを跨ぐ層別サンプル
- FOMO/Lateはpast-only入力とtriggered rulesを確認
- Averaging Down/Profit Pyramidingは追加前平均建値、追加価格、追加比率、stable fill orderを確認
- Revenge Candidateは前episode loss、gap、initial notional ratio、overlap除外を確認
- outcome、PnL、勝敗、MFE/MAEをレビュー画面へ含めない
- 実装バグと定義限界を分離する
- v1閾値は変更せず、変更提案は`v2_candidates.md`へ記録する

## 2. 100〜500口座・数千episodeへの拡大設計

- selection biasを抑えるwallet層化
- zero-to-zero再構成誤差0を維持する品質ゲート
- TWAP cap、continuity error、left censoringの除外
- 5分足5,000本制限を回避する継続collectorまたは固定期間設計
- label-side cell最低50件を目標に必要口座数・期間を見積もる
- exploratory用とheld-out confirmatory期間を事前分離

## 3. 引き続き禁止

- 24episodeから勝率・平均PnL・PF・有意差を結論化しない
- 「FOMOは負ける」「ナンピンは悪い」「逆張りすれば勝てる」と断定しない
- Crowdingはhistorical OI不足、Trapped/Liquidationは過去state不足のまま

# 作業終了時

- CURRENT_STATUS.md / NEXT_TASK.md / DECISIONS.md更新
- 全test実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ専用Discord通知
