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

# 完了: outcome-blind品質レビューと標本拡大設計

- 全TRUE 14episode＋層別all-FALSE 7episodeをレビューし21/21 PASS
- v1閾値変更なし
- add個別証跡不足をv2 pipeline候補として記録
- 100口座pilot→500口座、探索60%・validation 20%・held-out 20%、eligible 2,000episode目標を設計

# 次タスク: 100口座pilot準備

## 1. outcome-free add evidence table

- stable sequence index、timestamp、pre-add平均、add価格・数量、既存数量、size ratio、signed distance、分類を保存
- outcome/PnLは含めない
- v1判定と件数一致をtest化

## 2. 100口座候補の層化と固定

- volume、ROI/loss depth、activity、holding、market-cap exposure、fill frequencyで層化
- sampling manifestと固定end timeを保存
- 5分足継続collectorを先行し、API 5,000本制限を回避
- 100口座で再構成・会計誤差0と除外率を確認後だけ500口座へ拡大

## 3. 引き続き禁止

- 24episodeから勝率・平均PnL・PF・有意差を結論化しない
- 「FOMOは負ける」「ナンピンは悪い」「逆張りすれば勝てる」と断定しない
- Crowdingはhistorical OI不足、Trapped/Liquidationは過去state不足のまま

# 作業終了時

- CURRENT_STATUS.md / NEXT_TASK.md / DECISIONS.md更新
- 全test実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ専用Discord通知
