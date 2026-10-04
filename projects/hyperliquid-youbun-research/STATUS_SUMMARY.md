# STATUS_SUMMARY

更新: 2026-10-04 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

fixed-100 forward collector v1/v2はいずれもGitHub scheduled runの実間隔不足でGate FAILし凍結済み。
v2 rawは監査証跡として保持し、安定した外部schedulerを設計するまで収集を停止中。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- 上記subset: quantity mismatch 0 / continuity error 0
- v1 forward collector: FAIL / 凍結
- v1 scheduled interval: 約3〜4時間
- v1高頻度retention risk: P031 / P035
- v1 workflow: disabled
- v2 canary / fixed-100初回run: PASS
- v2初回scheduled run: FAIL（run `37169042021`）
- v2 scheduled interval: 直前full runから約3時間35分
- v2高頻度retention risk: P031 12,524 fills / P035 11,365 fills
- v2 workflow: `disabled_manually`、実行中・queued 0
- tests: 52 passed
- OHLCV / behavior label / 500-wallet expansion: HOLD

## Current Blocker

workflow内の5分cron設定だけでは実際の起動周期を保証できず、v2でも高頻度2口座が1run 10,000 fillsを超えた。GitHub Actions scheduleを正本schedulerにできない。

## Next

1. GitHub Actions scheduleに依存しない、20分以内の実行を観測可能なschedulerを設計する
2. timeout・重複起動・失敗時checkpoint非更新・data branch競合の扱いを事前登録する
3. 新しい保存namespaceとanalysis startでcanary → fixed-100初回run → 20分以内の連続runを確認する
4. retention risk / failure / cap / unresolved gap 0を確認してから7日Shadow Gateを開始する

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

欠落fill推定・前方補完・wallet差替えは禁止。v1/v2 raw/stateは監査用に保持し、次版へ混ぜない。
