# STATUS_SUMMARY

更新: 2026-10-04 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

fixed-100 forward collector v1はschedule間隔不足でGate FAILし凍結済み。
v2を`forward-data-v2/`へ完全分離し、新しいanalysis startで再開準備中。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- 上記subset: quantity mismatch 0 / continuity error 0
- v1 forward collector: FAIL / 凍結
- v1 scheduled interval: 約3〜4時間
- v1高頻度retention risk: P031 / P035
- v1 workflow: disabled
- tests: 51 passed
- OHLCV / behavior label / 500-wallet expansion: HOLD

## Current Blocker

v1はrun自体は成功したが、間隔が長く高頻度口座で1run 10,000 fills超となり完全性を保証できなかった。

## Next

1. v2をmainへ反映しworkflow再enable
2. 1-wallet canary → fixed-100初回run → 直後runを確認
3. retention risk / failure / cap 0なら、その時点を新しい7日Shadow Gate開始時刻として固定
4. Shadow中はGate evaluatorとcanonical reconstruction dry-runを並行実装

## Gate

PASS必須:
- scheduled run success 100%
- unresolved gap 0
- cap hit 0
- checkpoint rollback 0
- sample SHA不変
- raw corruption 0
- canonical continuity error 0
- quantity mismatch 0

## Last Important Decision

欠落fill推定・前方補完・wallet差替えは禁止。v1 raw/stateは監査用に保持し、v2へ混ぜない。
