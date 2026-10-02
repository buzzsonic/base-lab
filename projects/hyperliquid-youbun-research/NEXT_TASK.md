# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

# 運用方針

このファイルは「1工程だけ」で止めず、原則として2〜3工程を連続実行する。

各工程の品質ゲートをPASSした場合は、ユーザー確認を待たず次工程へ進む。
重大差異・仕様衝突・データ不足・安全上の懸念がある場合のみ停止する。

作業終了時は、その時点までの成果をまとめて
- CURRENT_STATUS.md
- NEXT_TASK.md
- 必要ならDECISIONS.md
へ反映し、test、commit、push、Discord通知まで行う。

養分ホイホイには変更を加えない。

---

# 現在地

完了:
- episode再構成 61/61 PASS
- 層別目視 20/20 PASS
- 会計照合 61/61 PASS
- 市場series coverage棚卸し完了
- PARTIAL 24episodeへpast-only特徴量付与済み
- future leakage test PASS
- 26 tests PASS

historical mark / OIは unavailable のためNULL維持。

---

# PHASE 1: 行動ラベルv1の事前登録

以下を事前登録する。

- FOMO_LONG / FOMO_SHORT
- LATE_LONG / LATE_SHORT
- AVERAGING_DOWN_LONG / SHORT
- PROFIT_PYRAMIDING_LONG / SHORT
- REVENGE_CANDIDATE

成果物:
`labels/preregistered-v1/`

最低限:
- README.md
- label_definitions.md
- label_config.json
- label_schema.json
- unit tests

要件:
- 閾値は24episodeの結果を見る前に固定
- required_featuresを明示
- missing featureはFALSEではなくUNAVAILABLE
- 1episode複数ラベル可
- Long/Shortはdirection-adjusted metricで共通実装
- config_versionを固定
- v1を後から上書きしない。変更はv2

Crowding / Trapped / Liquidation behaviorはまだ対象外。

## PHASE 1 Gate

以下がPASSしたらPHASE 2へ自動進行。

- label definitions完成
- config固定
- schema固定
- tests PASS
- future leakageなし
- Long/Short symmetry test PASS

---

# PHASE 2: 24episodeへのdry-run分類

PHASE 1の固定済みv1を、PARTIAL 24episodeへ適用する。

目的はpipeline検証であり、成績評価ではない。

各episodeについて保存:
- episode_id
- wallet匿名ID
- coin
- side
- 各label status: TRUE / FALSE / UNAVAILABLE
- label score
- triggered_rules
- missing_required_features
- config_version

集計:
- label availability件数
- TRUE / FALSE / UNAVAILABLE件数
- 重複ラベル件数
- Long / Short別件数
- wallet別件数

この段階では以下を結論化しない:
- 勝率
- 平均PnL
- PF
- 「FOMOは負ける」
- 「ナンピンは悪い」
- 「逆張りすれば勝てる」

## PHASE 2 Gate

以下がPASSしたらPHASE 3へ自動進行。

- 24episode全件出力
- schema validation PASS
- 再実行で同一結果
- UNAVAILABLE処理正常
- 重複ラベル正常
- no future leakage
- 明らかな実装バグなし

---

# PHASE 3: exploratory behavior summary

PHASE 2がPASSしたら、初回の探索的サマリを作る。

重要:
24episodeは標本が小さいため、統計的な結論ではなく「どの行動がどれくらい出るか」の分布確認に限定する。

出力:
`analysis/exploratory-behavior-v1/`

最低限:
- README.md
- label_counts.csv
- episode_labels.csv
- wallet_label_summary.csv

見る項目:
- FOMO候補件数
- Late候補件数
- Averaging Down件数
- Profit Pyramiding件数
- Revenge Candidate件数
- 重複パターン
- walletごとの偏り
- coinごとの偏り
- Long/Short偏り
- UNAVAILABLE率

PnL関連は参考値として別セクションに分離し、標本不足を明記する。
有意差・勝率優位・逆指標性の結論は出さない。

## PHASE 3 Gate

PHASE 3終了時に次の判断材料を作る。

- どのラベルが実際に十分発生するか
- どのラベルがほぼ発生しないか
- どのseries不足がボトルネックか
- 標本拡大時に優先すべきラベル
- v1定義で明らかな不自然さがあるか
- v2を作る必要があるか

v2が必要な場合もv1結果を保存したまま別versionで作る。

---

# 停止条件

以下の場合のみ途中停止して報告する。

- 重大な再構成差異
- データ破損
- v1定義と実データ構造の根本的不整合
- 既存テストの回帰
- future leakage検出
- GitHub競合
- 仕様判断が研究結果を大きく左右し、既存DECISIONS.mdで解決できない場合

軽微な閾値・命名・ファイル構成は合理的に決めて続行する。

---

# 作業終了時

必ず:
- CURRENT_STATUS.md更新
- NEXT_TASK.md更新
- 必要ならDECISIONS.md追記
- 全test実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discord通知

完了報告には
1. どこまで進んだか
2. 各PHASEの結果
3. 停止理由があればその理由
4. 次に何をするか
を短く明記する。
