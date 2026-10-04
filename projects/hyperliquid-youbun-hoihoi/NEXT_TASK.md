# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分ホイホイ関連commit差分だけ確認する。
`CURRENT_STATUS.md` / 品質レポート / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

BTC forward v1をtimer無効の1-wallet canaryで検証する。

契約正本: `contracts/btc-research-sample-v0.1/`
収集契約: `BTC_FORWARD_COLLECTION_CONTRACT.md`

### 1. Canary Entrypoint

- walletを明示指定する手動entrypointを作る
- 通常fillsとTWAP slicesを各1回取得する
- data branchへ保存せずartifactのみとする
- `analysis_start_ms`以前のrowを研究windowへ混ぜない

### 2. Canary Gate

- source sequenceの欠落・重複0
- endpoint failure / page cap / retention risk 0
- 同一timestampのsource orderがAPI responseと一致
- 通常fill＋TWAPのposition chainが一意、または曖昧理由を保存

### 3. Overlap Re-run

- 同じwalletを20分overlap付きで再実行する
- raw重複を残し、canonical viewはfirst-seen rowを維持する
- checkpointが成功時だけ進み、失敗時は進まないことを確認する

### 4. Expansion Gate

1. canary 2回のraw/canonical/stateを目視照合する
2. 少数wallet 24時間の所要時間・API weight・欠測を測る
3. Gate通過後だけ100/200 wallet forward windowを開始する
4. 7成功JST日後にv0.1を再適用する
5. 養分くん側の受入確認後だけhandoff versionを固定する

## Existing Snapshot

- current: complete 79 / incomplete 21、79 walletsが成功3日
- shadow: complete 97 / incomplete 3、97 walletsが成功2日
- shadow flags: BOT 27 / MM 4 / farm 6
- research sample: 0
- BTC research selection: `btc-research-selection-v0.1.0-draft`
- BTC handoff schema: `hoihoi-btc-handoff-v0.1`
- contract tests: 36 PASS
- dry-run: current 0 / shadow 0 handoff eligible、39 tests PASS
- preliminary except observation/TWAP/market: current 0 / shadow 2（適格ではない）
- forward contract/order primitives: 43 tests PASS、live canary NOT RUN
- canary collector/manual workflow: 47 tests PASS、scheduleなし、live canary NOT RUN
- weekly: run 37172824334 success / JST report `2026-10-04` / data `1b7786e`
- 1,000-wallet expansion: HOLD（当面は非優先）

## Scope Boundary

養分ホイホイが行う:

- wallet discovery / classification / maintenance
- BTC行動episodeとprofileの品質管理
- version付きsample handoff

養分くんが行う:

- wallet行動とBTC価格帯・市場局面の結合
- event window、対照群、markout、その後の価格反応の分析

禁止: 市場反応を見てwalletを選ぶこと、欠測を成功扱いすること、7日観察前の即時昇格、自動売買、秘密鍵取得、未承認の自動handoff採用、1,000-wallet拡大の先行実施。
