# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分くん関連commit差分だけ確認する。
`CURRENT_STATUS.md` / `DECISIONS.md` / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

fixed-100 forward collector v1はGate FAILで凍結済み。
v2を `forward-data-v2/` に完全分離し、新しいanalysis startで再開する。

1. v2をmainへ反映しworkflow再enable
2. 1-wallet canary
3. fixed-100初回run
4. 直後runまで確認
5. retention risk / endpoint failure / cap / data branch conflict が0なら新しい7日Shadow Gate開始時刻を固定

v1 raw/stateをv2へ混ぜない。

## Shadow中に並行実装

- Shadow Gate evaluator
- 中間quality summary
- canonical fills / TWAP / Funding merge dry-run
- episode reconstruction dry-run

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
