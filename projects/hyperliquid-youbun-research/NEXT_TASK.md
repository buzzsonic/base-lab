# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

# 運用方針

原則として2〜3工程を連続実行する。
各工程の品質ゲートをPASSしたら、ユーザー確認を待たず次工程へ進む。

停止するのは以下のみ:
- 重大な再構成差異
- 会計差異
- future leakage
- データ破損
- sampling leakage
- API制約で設計変更が必要
- GitHub競合
- 仕様判断が研究結果を大きく左右し、既存DECISIONS.mdで解決不能

軽微な閾値・命名・ファイル構成は合理的に決めて続行する。

養分ホイホイには変更を加えない。

---

# 現在地

完了:
- episode再構成 61/61 PASS
- 層別目視 20/20 PASS
- 会計照合 61/61 PASS
- 市場coverage棚卸し完了
- PARTIAL 24episodeへpast-only特徴量付与
- behavior label v1.0.0事前登録
- 24episode dry-run完了
- exploratory behavior summary完了
- outcome-blindレビュー 21/21 PASS
- 38 tests PASS
- v1閾値凍結済み

次は100口座pilotへ進む。

---

# PHASE 1: outcome-free add evidence table【完了】

- add events 2,464件
- source trace不明0
- dry-run Averaging Down 4件 / Profit Pyramiding 8件と一致
- outcome列なし
- 39 tests PASS

目的:
AVERAGING_DOWN / PROFIT_PYRAMIDINGの根拠を、個々の追加fill単位で監査可能にする。

各add eventについて保存:
- wallet_anon_id
- episode_id
- stable_sequence_index
- timestamp
- coin
- side
- pre_add_position_size
- pre_add_avg_entry_price
- add_price
- add_qty
- add_notional
- add_size_ratio_vs_existing
- signed_price_distance_vs_pre_add_avg
- favorable_or_adverse
- resulting_position_size
- label_v1_classification
- source_fill_id または stable trace key

原則:
- PnL
- episode outcome
- MFE / MAE
- 勝敗
- post-entry market data
は含めない。

成果物:
`evidence/add-events-v1/`

最低限:
- README.md
- add_events.csv
- schema.md

テスト:
- add件数がv1分類と整合
- Averaging DownとProfit Pyramidingが相互に正しく分離
- Long/Short対称性
- stable sequence再現性
- source fill trace可能
- outcome列が存在しない

## PHASE 1 Gate

PASS条件:
- add evidence table生成成功
- v1ラベル件数と一致
- trace不明0
- tests PASS

PASS後PHASE 2へ進む。

---

# PHASE 2: 100口座pilot sampling manifest作成【次】

開始条件: 行動ラベル結果を含まないdiscovery universeをCSV/JSONで正本化する。現在mainには固定可能な候補universeがないため、候補を推測して100口座を作らない。

目的:
100口座を固定し、探索用pilotを再現可能にする。

## サンプリング原則

養分ホイホイ由来の候補または既存discovery universeから選ぶ場合でも、
養分くん側では「行動結果やPnLを見て選ばない」。

層化軸:
- account size / equity proxy
- fill frequency
- holding time
- BTC/ETH中心 / alt中心 / small-alt中心
- activity level
- volume
- loss depth / ROI系指標を使う場合は、sampling biasを招かないよう層化変数としてのみ使用し、行動ラベル結果を見て選ばない
- source diversity

固定するもの:
- sampling_manifest.csv
- sample_version
- fixed_end_time
- discovery source
- inclusion reason
- exclusion reason
- stratum

100口座を固定後、途中差し替えしない。
API失敗等の技術除外は別記録にする。

## split設計

最終500口座拡大を見据え、
- exploratory 60%
- validation 20%
- held-out 20%
の概念をmanifestへ持たせる。

pilot 100では将来split seedを固定しておく。

## PHASE 2 Gate

PASS条件:
- 100 wallet IDs固定
- duplicate 0
- sampling manifest再生成で同一
- strata分布記録済み
- outcome/behavior labelでの選抜なし

PASS後PHASE 3へ進む。

---

# PHASE 3: 100口座pilot収集・再構成準備

目的:
500口座拡大前に、100口座でデータ品質・API負荷・除外率を測る。

## 収集対象

各walletについて可能な範囲で:
- raw fills
- TWAP
- Funding
- account / position continuity情報
- 5分OHLCV
- 必要なBTC基準series

historical mark / OIは取得不能ならNULL維持し、推定しない。

## 5分足

公式5,000本制限を回避するため、
継続collector / cacheを優先して実装する。

今後のpilot以降では「後から17日分しかない」問題を減らす。

保存:
- collector checkpoint
- last successful timestamp
- coin別coverage
- fetch failures
- retry status

## 再構成品質

100口座pilotで必ず測る:
- raw fills件数
- reconstructed episode数
- completed episode数
- quantity mismatch
- continuity error
- TWAP cap hit
- perp fill 0
- excluded wallets
- accounting mismatch
- FEATURE_READY / PARTIAL / NOT_READY
- API error / retry count

## 500口座へ進むGate

以下を満たすまで500へ進まない:
- quantity mismatch 0
-重大 accounting mismatch 0
- continuity errorが説明可能
- 除外率が許容範囲
- API負荷が運用可能
- collector checkpoint正常
- sampling manifest固定
- test回帰なし

除外率やcap率が高すぎる場合は500へ進まず原因分析を優先。

---

# PHASE 4: pilot結果サマリ【PHASE 3 PASS時】

100口座pilot結果をまとめる。

成果物:
`analysis/pilot-100-v1/`

最低限:
- README.md
- wallet_quality_summary.csv
- episode_quality_summary.csv
- coverage_summary.csv
- exclusion_reasons.csv

まだ行わない:
- behavior別勝率結論
- PF比較
- 有意差主張
- 逆指標性の結論

ここでは「500口座へ拡大してよい品質か」を判断する。

---

# 作業終了時

必ず:
- CURRENT_STATUS.md更新
- NEXT_TASK.md更新
- 必要ならDECISIONS.md追記
- 全test実行
- 養分くん対象ファイルのみcommit/push
- push成功後のみ養分くん専用Discord通知

完了報告には:
1. PHASE 1〜4のどこまで進んだか
2. 各GateのPASS/FAIL
3. 100口座pilotの主要品質指標
4. 500口座へ進めるか
を短く明記する。
