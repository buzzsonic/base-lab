# STATUS_SUMMARY

更新: 2026-10-04 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

fixed-100 forward collector v1/v2はいずれもGitHub scheduled runの実間隔不足でGate FAILし凍結済み。
v3はVPS上のDocker + systemd timerを正本schedulerにする方針へ切替済み。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- 上記subset: quantity mismatch 0 / continuity error 0
- v1 forward collector: FAIL / 凍結
- v1 scheduled interval: 約3〜4時間
- v1高頻度retention risk: P031 / P035
- v2 canary / fixed-100初回run: PASS
- v2初回scheduled run: FAIL（run `37169042021`）
- v2 scheduled interval: 約3時間35分
- v2高頻度retention risk: P031 12,524 fills / P035 11,365 fills
- v1/v2 workflow: disabled
- tests: 55 passed
- v3 VPS runtime package: 実装済み、local 55 tests PASS
- v3 Docker build: local Docker daemon応答停止のため未確定。PR CIで検証する
- OHLCV / behavior label / 500-wallet expansion: HOLD

## Current Decision

GitHub Actions scheduleは正本schedulerにしない。
v3はUbuntu VPS + Docker + systemd timerを正本とし、5分起動要求・実測20分以内を品質要件にする。
GitHub Actionsはtest / 手動canary / fallback診断に限定する。

## Next

1. PR CIで55 testsとVPS Docker image buildを確認
2. VPSへ配置し、timerを有効化する前に1-wallet canary
3. fixed-100を3回以上連続実行し、実測間隔・duration・quality flagを確認
4. 全run実測20分以内、retention risk / failure / cap / gap 0ならv3 analysis startを固定し7日Shadow Gate開始

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

欠落fill推定・前方補完・wallet差替えは禁止。v1/v2 raw/stateは監査用に保持し、v3へ混ぜない。
