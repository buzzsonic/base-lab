# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 現在地

- historical pilot: 不採用（rolling retentionにより56/100口座を技術除外）
- eligible 44口座・完結22,973episode: quantity mismatch 0 / continuity error 0
- fixed-100 forward collector: 実装・単体test・1口座ローカルcanary PASS
- OHLCV / behavior label / 500口座拡大: HOLD

## 次の実行単位: 7日Shadow Collection開始

1. collector変更をmainへmergeする。
2. GitHub Actionsを`max_wallets=1`で手動実行し、data branchへのraw/state保存とpushを確認する。
3. canary成功後、`max_wallets`を空にして固定100口座runを実行する。
4. schedule（20分周期）を維持し、最低7日間のshadow evidenceを蓄積する。
5. 各runのmanifestとcheckpointから品質サマリを作る。

## Shadow Gate

以下をすべて満たすまでpilot分析を再開しない。

- scheduled run成功率100%
- 100 wallet×必須endpointの未解消gap 0
- page safety cap hit 0
- checkpoint巻き戻り0
- sampling manifest SHA不変
- raw run file破損0
- canonical fill continuity error 0
- quantity mismatch 0

record 0のrunは、それだけでは失敗ではない。API成功、対象期間、checkpoint、前後runとのcoverageを合わせて判定する。

## 停止条件

- raw evidenceで説明できないquantity mismatch / continuity error
- accounting mismatch
- future leakage / sampling leakage
- data branch競合またはraw破損
- API retention / rate limit / page capにより固定周期で完全性を維持できない
- sampling manifest変化
- 研究結果を大きく左右する未決仕様

停止条件に当たらなければ、7日Gate判定まで収集を継続する。欠落fill推定、前方補完、口座差替えは禁止。

## Gate PASS後のみ

1. fixed periodを凍結
2. canonical fillsへTWAPを統合
3. zero-to-zero episode再構成と会計照合
4. OHLCV / BTC reference収集とcoverage判定
5. past-only featureとlabel v1 availability確認
6. 500口座Gate判断

## 作業終了時

- `CURRENT_STATUS.md` / `NEXT_TASK.md` / 必要なら`DECISIONS.md`更新
- 全test実行
- 養分くん対象ファイルだけcommit/push
- main反映と実行結果を確認してから専用Discordへ通知
