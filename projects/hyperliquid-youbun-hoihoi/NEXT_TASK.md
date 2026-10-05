# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分ホイホイ関連commit差分だけ確認する。
`CURRENT_STATUS.md` / 品質レポート / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

BTC forward v1の5-wallet・24時間canaryを完走させ、TWAPとoverlapの実証を監査する。

契約正本: `contracts/btc-research-sample-v0.1/`
収集契約: `BTC_FORWARD_COLLECTION_CONTRACT.md`

### 1. Completed Canary Evidence

- PR #45 / merge `b2dcbf21`で同一workflow内の2回収集とfail-closed監査を追加
- run `37328123994` PASS
- raw 14 / BTC 12 / TWAP 0 / BTC 5m 25本×2run
- source sequence欠落0、gap 0、cap 0、continuity error 0、same-ms ambiguity 0
- stateは2回目成功へ進み、legacy checkpoint/data branchは不変
- ただしoverlap期間の新規rowがなく、raw重複は0
- PR #48 / merge `d6350567`で5-wallet固定windowを実装
- initial run `37330544150` PASS、data `a0d35cca`
- 観察期間: 2026-10-06 00:15:45 JST〜2026-10-07 00:15:45 JST
- state/config SHA/legacy分離を確認。自動sample昇格はfalse

### 2. Running Canary Gate

- 5 walletを24時間観察し、TWAP実rowまたはoverlap重複を得る
- raw重複を残し、canonicalがfirst-seen rowを維持することを実データで確認する
- 同一timestampの通常fill＋TWAP chainは一意な場合だけ採用し、曖昧ならFAILを維持する
- 空応答を「順序検証済み」とは扱わない

### 3. Durable Window Design

- canary artifactからpromotionせず、legacyと完全分離した新state/data rootを定義する
- 成功JST日はfills/TWAP/marketのrequired endpointが全て成功した日のみ加算する
- schedule遅延、cap、gap、順序不明、state rollbackは当日失敗として扱う

### 4. Expansion Gate

1. 少数wallet 24時間の所要時間・API weight・欠測を測る
2. TWAP/overlapの実row Gateを通す
3. Gate通過後だけ限定cohortのforward windowを開始する
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
- canary collector/manual workflow: 49 tests PASS
- live canary: run 37328123994 PASS、BTC 12、TWAP 0、overlap重複0のためpartial evidence
- 24h canary: `CANARY24H_RUNNING`、51 tests PASS、initial run 37330544150、data `a0d35cca`
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
