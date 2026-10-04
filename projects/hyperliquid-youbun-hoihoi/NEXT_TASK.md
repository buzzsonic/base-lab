# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分ホイホイ関連commit差分だけ確認する。
`CURRENT_STATUS.md` / 品質レポート / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

current cohortとshadow cohortを日次観察し、7成功JST日まで品質を蓄積する。

1. shadowのcomplete→incomplete 1 walletを追跡
2. farm疑い6件・単一銘柄MM疑いを重点確認
3. weekly比較レポートを継続し、7日到達時のGateを判定
4. current / shadowの7日比較とAPI所要時間Gateを判定
5. Gate PASS時のみcohort置換/統合と1,000-wallet expansionを検討

## Current Snapshot

- current: complete 79 / incomplete 21、79 walletsが成功3日
- shadow: complete 97 / incomplete 3、97 walletsが成功2日
- shadow flags: BOT 27 / MM 4 / farm 6 / small-alt 11
- research sample: 0
- weekly: run 37172824334 success / JST report `2026-10-04` / data `1b7786e`
- 1,000-wallet expansion: HOLD

禁止: 欠測・retention gapを成功日に数えること、7日観察前の即時昇格、shadowからcurrent registryへの早期置換。
