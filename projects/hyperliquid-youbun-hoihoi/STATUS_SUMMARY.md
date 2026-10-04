# STATUS_SUMMARY

更新: 2026-10-04 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分ホイホイ関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / 品質レポート / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

現行cohortとshadow cohortを並行観察中。7日観察完了前なのでresearch sample昇格・cohort置換・1,000-wallet拡大はHOLD。

## Key Status

- current discovery pool / selected: 200 / 100
- current cohort: complete 79 / incomplete 21
- current successful observation days: 79 wallets = 3 days, 21 wallets = 0
- shadow cohort: complete 97 / incomplete 3
- shadow successful days: 97 wallets = 2 days, 1 wallet = 1 day, 2 wallets = 0
- shadow flags: BOT 27 / MM 4 / farm 6 / small-alt 11
- current sample: 0
- shadow sample: 0
- weekly comparison: run 37172824334 success / data `1b7786e`
- 1,000-wallet expansion: HOLD

## Current Blocker

7日間・7 JST日分の完全取得Gateが未達。
shadowで1 walletがcomplete→incompleteへ変化しており、retention/gapがlookback外へ出るまでpromotion禁止。

## Next

1. current / shadowを日次観察し7成功JST日まで蓄積
2. shadowのcomplete→incomplete 1 walletとfarm/MM疑いを重点監査
3. weekly比較のJSTレポートを継続し、7日到達時にpromotion・置換Gateを判定
4. 7日比較とAPI所要時間Gateを通過した場合のみcohort置換/統合と1,000-wallet拡大を検討

## Comparison Snapshot

shadowはcurrent比で:
- complete history: +18 wallets
- BOT suspected: -11
- MM suspected: -8
- small-alt-centric: +9

ただし7日Gate未達のため優劣確定・置換はまだしない。

## Last Important Decision

欠測・retention gapは成功観察日に数えない。7日観察前の即時昇格は禁止。shadowは現行registryを変更しない隔離namespaceで運用する。weeklyはJST日付・専用queueでreportのみを保存する。
