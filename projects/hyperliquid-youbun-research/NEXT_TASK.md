# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 現在地

- historical pilot: 不採用（rolling retentionにより56/100口座を技術除外）
- eligible 44口座・完結22,973episode: quantity mismatch 0 / continuity error 0
- fixed-100 forward collector: main反映・GitHub canary・固定100口座初回run PASS
- analysis start: `2026-10-03 21:12 JST` (`1791029567198` ms)
- data branch: 300/300 checkpoint、failure 0、cap hit 0、retention risk 0
- OHLCV / behavior label / 500口座拡大: HOLD
- 7日Shadow Collection終了予定: `2026-10-10 21:12 JST`

# 運用方針

Shadow Collectionは20分周期のまま継続する。
7日経過を待つ間も停止せず、Gate判定に必要な検証ツールと中間品質監査を実装する。

原則2〜3工程を連続実行し、各Gate PASS後はユーザー確認を待たず次へ進む。

養分ホイホイ側は変更しない。

---

# PHASE 1: Shadow Gate自動判定ツール【最優先】

7日終了後に手作業集計しなくて済むよう、data branchのrun manifest / checkpoint / raw filesからShadow Gateを機械判定する。

最低限集計:
- scheduled_runs_expected
- scheduled_runs_observed
- scheduled_run_success_rate
- wallet_endpoint_expected
- wallet_endpoint_completed
- unresolved_gap_count
- failure_count
- retry_count
- cap_hit_count
- retention_risk_count
- checkpoint_rollback_count
- sample_manifest_sha_changes
- raw_file_count
- raw_corruption_count
- duplicate_raw_rows
- canonical_fill_rows
- canonical_twap_rows
- canonical_funding_rows
- continuity_error_count
- quantity_mismatch_count

出力:
`shadow/quality-gate-v1/`

最低限:
- `README.md`
- `shadow_quality_summary.json`
- `run_quality.csv`
- `wallet_endpoint_quality.csv`
- `gate_result.json`

`gate_result.json` は各条件ごとに PASS / FAIL / NOT_YET_EVALUABLE と根拠数値を持つ。

7日未経過時は期間条件だけ `NOT_YET_EVALUABLE` とし、途中データでもその他の品質チェックは実行可能にする。

## Shadow Gate条件

- scheduled run成功率 100%
- 100 wallet×必須endpointの未解消gap 0
- page safety cap hit 0
- checkpoint巻き戻り 0
- sampling manifest SHA不変
- raw run file破損 0
- canonical fill continuity error 0
- quantity mismatch 0

record 0のrunは単独ではFAILにしない。
API成功・対象期間・checkpoint・隣接runとのcoverageで判定する。

## PHASE 1 Gate

- evaluator再実行で同一結果
- synthetic failureを正しくFAIL判定
- record 0正常runを誤FAILしない
- missing manifest / broken raw / rollbackを検知
- tests PASS

PASS後PHASE 2へ進む。

---

# PHASE 2: 中間Shadow品質dry-run

現在まで蓄積済みのforward dataだけを使ってShadow evaluatorを実行する。

目的は最終判定ではなく、7日終了前に異常を早期発見すること。

確認:
- 現時点run成功率
- unresolved gaps
- cap / retention risk
- raw corruption
- checkpoint monotonicity
- sample SHA固定
- endpoint別record増分
- wallet別coverage

異常があれば即停止し原因修正。
異常がなければ収集継続。

成果物:
`shadow/interim-2026-10-04/`

最低限:
- `README.md`
- `interim_quality.json`
- `run_anomalies.csv`
- `wallet_anomalies.csv`

---

# PHASE 3: canonical fills再構成dry-run

7日完了前でも、analysis_start以降に蓄積したデータを使ってcanonical merge/reconstructionをdry-runする。

対象:
- normal fills
- TWAP slice fills
- Funding

契約:
- inclusive boundary overlap
- dedup key固定
- same timestampはstartPosition chainでinterleave
- source endpoint保存
- raw order / ingested_at保存
- 欠落推定禁止

再構成確認:
- zero-to-zero episode
- partial close
- add
- reversal
- quantity continuity
- startPosition continuity
- Funding attribution

途中期間なので未完episodeはcensoredとして扱う。

集計:
- canonical fills
- completed episodes
- censored episodes
- quantity mismatch
- continuity errors
- unexplained errors

## PHASE 3 Gate

途中データ時点で:
- unexplained quantity mismatch 0
- unexplained continuity error 0
- raw→canonical再実行同一
- sample manifest不変
- tests PASS

PASSしても7日Shadow Gate完了まではOHLCV / label / 500口座へ進まない。

---

# PHASE 4: 7日終了後の最終Shadow Gate

`2026-10-10 21:12 JST`以降のみ実行。

PHASE 1 evaluatorを固定期間全体へ実行する。

全Gate PASSなら:
1. fixed analysis periodを凍結
2. canonical fills / TWAP / Fundingを確定
3. episode再構成・会計照合
4. OHLCV / BTC reference収集
5. market coverage判定
6. past-only feature生成
7. label v1 availability確認
8. pilot-100品質サマリ
9. 500口座Gate判断

Gate FAILなら:
- 500口座へ進まない
- 原因を分類
- gap補完のための推定は禁止
- 必要ならShadow期間を新しいversionとして再開始

---

# 停止条件

- raw evidenceで説明できないquantity mismatch / continuity error
- accounting mismatch
- future leakage / sampling leakage
- data branch競合またはraw破損
- API retention / rate limit / page capにより固定周期で完全性を維持できない
- sampling manifest変化
- collector schedule欠落を復旧不能
- 研究結果を大きく左右する未決仕様

停止条件に当たらなければ、7日Gate判定まで収集と品質検証を並行継続する。
欠落fill推定、前方補完、口座差替えは禁止。

---

# 作業終了時

必ず:
- `CURRENT_STATUS.md` 更新
- `NEXT_TASK.md` 更新
- 必要なら `DECISIONS.md` 更新
- 全test実行
- 養分くん対象ファイルだけcommit/push
- main反映と実行結果確認後のみ専用Discord通知

完了報告には:
1. PHASE 1〜3のどこまで完了したか
2. 現時点Shadow品質数値
3. 異常の有無
4. 7日Gateまで残っている条件
を短く明記する。
