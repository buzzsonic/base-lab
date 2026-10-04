# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分くん関連commit差分だけ確認する。
`CURRENT_STATUS.md` / `DECISIONS.md` / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

fixed-100 forward collector v1/v2はGate FAILで凍結済み。
GitHub Actions scheduleに依存しないschedulerを設計し、次版の観測契約を事前登録する。

1. 20分以内の起動を実測・監視できるscheduler候補を比較する
2. timeout、重複起動、retry、checkpoint、data branch競合、通知条件を設計する
3. `forward-data-v3/`等の新namespaceと新analysis startを事前登録する
4. 1-wallet canary → fixed-100初回run → 20分以内の連続runを確認する
5. retention risk / endpoint failure / cap / unresolved gap / data branch conflict が0なら新しい7日Shadow Gate開始時刻を固定

v1/v2 raw/stateを次版へ混ぜない。scheduler確定前にworkflowを再enableしない。

## Shadow中に並行実装

- Shadow Gate evaluator
- 中間quality summary
- canonical fills / TWAP / Funding merge dry-run
- episode reconstruction dry-run

ただしscheduler未確定中は、新しい観測データを前提にした本分析へ進まない。

## Gate

以下がすべて必要:
- scheduled run success 100%
- unresolved gap 0
- cap hit 0
- checkpoint rollback 0
- sample SHA不変
- raw corruption 0
- canonical continuity error 0
- quantity mismatch 0

Gate完了まではOHLCV本分析・behavior label本適用・500-wallet expansionはHOLD。

禁止: 欠落fill推定、前方補完、wallet差替え。
