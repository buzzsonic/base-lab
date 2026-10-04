# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分ホイホイ関連commit差分だけ確認する。
`CURRENT_STATUS.md` / 品質レポート / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

BTC sample dry-runで判明したraw品質不足を解消する新forward collection contractを設計する。

契約正本: `contracts/btc-research-sample-v0.1/`

### 1. Stable-order Raw Contract

- API response内の同一timestamp順を保持し、deduplicate時も順序を壊さない
- 既存hash順checkpointはlegacyとして修復・昇格に使わない
- append-only rawとcanonical viewを分離し、source orderを監査可能にする

### 2. TWAP Raw Contract

- `userTwapSliceFillsByTime`を通常fillsと別raw sourceで取得する
- endpoint cap、gap、checkpoint、dedup keyを独立管理する
- 統合時は同一timestampの`startPosition`鎖を使い、解けない順序はUNAVAILABLEにする

### 3. New Forward Window

- current / shadowの既存観察を壊さず、BTC研究用raw namespaceを新設する
- 最低7成功JST日、unresolved gap 0、同一ms未解決0、TWAP cap 0を要求する
- entry以前のBTC market windowだけを保存し、post-entry outcomeは扱わない

### 4. Re-run and Handoff Acceptance

1. v0.1を新forward windowへ再適用する
2. 適格数、除外理由、profile missingnessを報告する
3. 少数walletをoutcome-blindで目視照合する
4. 養分くん側でschema・hash・重複を検証する
5. 問題がなければhandoff versionを固定する

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
