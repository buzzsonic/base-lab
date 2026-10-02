# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

# 運用方針

原則2〜3工程を連続実行する。
各Gate PASS後はユーザー確認を待たず次工程へ進む。

停止条件:
- 重大な再構成差異
- 会計差異
- future leakage
- sampling leakage
- データ破損
- API制約で設計変更が必要
- GitHub競合
- 研究結果を大きく左右する未決仕様

軽微な命名・ファイル構成・実装詳細は合理的に決めて続行する。

養分ホイホイのコード・状態ファイルは変更しない。
ただし候補universeは読み取り専用のsourceとして参照してよい。

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
- outcome-free add evidence 2,464件
- add trace不明0
- 39 tests PASS

---

# STOPPED GATE: pilot-100再構成差異の原因監査

PHASE 1 PASS:
- Hoihoi public Trades固定commitの598 walletから100 walletをoutcome-freeに固定
- duplicate 0、25 strata、再生成同一、split 60/20/20

PHASE 2 partial PASS:
- fills / TWAP / Fundingは100/100 wallet成功、失敗0
- OHLCV / BTC referenceは停止条件到達のため未収集

PHASE 3 FAIL:
- quantity mismatch 107 episodes / 33 wallets
- continuity error 3,790 / 47 wallets

次に行うこと:
1. mismatch全107件をraw fill traceへ戻し、coin・wallet・timestamp・反転・同時刻・TWAP追加有無で分類する。
2. continuity error全3,790件をAPI page boundary、重複tid、TWAP merge、期間開始前positionに分類する。
3. `userFillsByTime`のページ間順序と同一timestamp順序が保存されているか検証する。
4. 修正は原因を証明できる場合だけ行い、欠落fillの推定や前方補完は禁止する。
5. quantity mismatch 0かつcontinuity errorが説明・除外可能になったら全43+ testsを再実行する。

再開Gate:
- quantity mismatch = 0
- 重大 accounting mismatch = 0
- continuity errorがraw evidenceで説明可能
- sampling manifest不変
- future leakage test PASS

Gate PASS後のみ、未実行のOHLCV / BTC series収集へ戻る。

---

# ARCHIVE: PHASE 1: 養分ホイホイ候補universeを読み取り専用で正本化

目的:
100口座pilotのsampling sourceを固定する。

参照元:
`projects/hyperliquid-youbun-hoihoi`

ホイホイ側の現状:
- candidate wallets 100
- discovery pool 200
- 新discovery runtimeではwallet 673観測
- public Trades実時間wallet 598
- 小型アルト12/12銘柄観測
- data branchへraw / market snapshot / coverage保存済み
- observationは進行中

原則:
- 養分ホイホイ側は読み取り専用
- ホイホイの候補選抜ロジックを変更しない
- 養分くん側へ必要なwallet ID / strata metadataだけsnapshotとして固定する
- behavior labels / PnL / outcomeをsamplingに使わない

成果物:
`sampling/pilot-100-v1/`

最低限:
- `source_manifest.json`
- `sampling_manifest.csv`
- `README.md`

source_manifest.json:
- source_project
- source_branch / source_commit
- source_data_version
- fixed_end_time
- source files
- selection seed
- selection algorithm version

sampling_manifest.csv:
- wallet
- anon_wallet_id
- source
- stratum
- size_band
- frequency_band
- symbol_tendency
- activity_band
- split
- inclusion_reason
- exclusion_reason
- sample_version

100 walletを固定する。
途中差替え禁止。
技術除外は別記録。

split:
- exploratory 60
- validation 20
- held_out 20

## Gate
- 100 wallet固定
- duplicate 0
- 再生成で同一
- source commit固定
- outcome / behavior label非使用
- strata分布保存

PASS後PHASE 2へ進む。

---

# PHASE 2: 100口座pilot収集

固定100口座に対して収集する。

対象:
- raw fills
- TWAP
- Funding
- continuity情報
- 5分OHLCV
- BTC基準series
- 必要なmarket snapshots

historical mark/OIは取得不能ならNULL。
推定・0埋め禁止。

取得はcheckpoint方式。
保存:
- wallet checkpoint
- endpoint checkpoint
- last success timestamp
- retries
- failures
- completeness
- cap/retention flags

5分足は継続collector/cacheを使い、5,000本制限の影響を減らす。

## 収集品質集計
- requested wallets
- completed wallets
- partial wallets
- failed wallets
- raw fills
- TWAP cap hits
- retention hits
- Funding coverage
- OHLCV coverage
- API retries/errors

---

# PHASE 3: 100口座再構成・品質Gate

収集後に既存episode pipelineを適用。

必須集計:
- reconstructed episodes
- completed episodes
- quantity mismatch
- continuity errors
- accounting mismatch
- excluded wallets
- exclusion reasons
- FEATURE_READY / PARTIAL / NOT_READY
- add events
- label availability
- endpoint cap / retention影響

品質条件:
- quantity mismatch = 0
-重大 accounting mismatch = 0
- continuity errorは説明可能
- sampling manifest固定
- checkpoint正常
- future leakage test PASS
- 全test回帰なし

上記PASSならPHASE 4へ。

---

# PHASE 4: pilot-100品質サマリ

成果物:
`analysis/pilot-100-v1/`

最低限:
- README.md
- wallet_quality_summary.csv
- episode_quality_summary.csv
- coverage_summary.csv
- exclusion_reasons.csv
- api_quality_summary.csv
- sampling_summary.csv

結論は「500口座へ拡大可能か」の品質判断に限定。

まだ禁止:
- behavior別勝率の結論
- PF比較
- 有意差
- 逆指標性
- FOMO/ナンピンの善悪評価

## 500口座Gate

GO条件:
- quantity mismatch 0
-重大 accounting mismatch 0
- 除外率が許容
- cap/retention影響が把握可能
- API負荷が運用可能
- 5分足collector継続可能
- sampling biasなし
- test PASS

FAIL時:
500へ進まず、原因別に修正案をNEXT_TASKへ記載。

GO時:
次のNEXT_TASKを500口座拡大バッチへ自動更新する。

---

# 作業終了時

必ず:
- CURRENT_STATUS.md更新
- NEXT_TASK.md更新
- 必要ならDECISIONS.md追記
- 全test実行
- 養分くん対象ファイルのみcommit/push
- push成功後のみ養分くん専用Discord通知

完了報告:
1. どのPHASEまで完了
2. 100口座pilot主要数値
3. Gate PASS/FAIL
4. 500口座へ進めるか
