# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分ホイホイ関連commit差分だけ確認する。
`CURRENT_STATUS.md` / 品質レポート / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

v0.1 draft契約を現行100件とshadow 100件へoutcome-blindでdry-runし、BTC研究適格性と欠測を測る。

契約正本: `contracts/btc-research-sample-v0.1/`

### 1. BTC Episode Coverage Builder

- BTC fillsだけをstable server orderで抽出する
- `startPosition`・side・sizeからzero-to-zero episodeを再構成する
- entry / add / reduce / close / reversal件数を保存する
- quantity mismatch、continuity error、retention gap、期間端censoringをwallet別に保存する
- 現行registryを上書きせず、dry-run成果物を別namespaceへ保存する

### 2. Selection Dry-run

- 7成功JST日、BTC 3活動日、20 fills、5完結episodeを初期Gateとして適用する
- BOT / MM / arbitrage / funding arbitrage / farm疑いを除外する
- 適格数だけでなく、全walletの複数除外理由とUNAVAILABLEを保存する
- cohort別の差は報告するが、適格数を増やすために同じversionの閾値を変更しない

### 3. Behavior Profile Dry-run

- ナンピン候補は5% size・5bp adverseの既存事前登録定義を再利用する
- size急拡大候補は直前5完結BTC episodeのinitial notional中央値に対する2倍を初期値とする
- 高値飛び乗り候補はentry以前の市場windowが無ければ`UNAVAILABLE`にする
- TRUE / FALSEは最低3 episodeの根拠を要求し、欠測をFALSEへ変換しない

### 4. Validation and Handoff Acceptance

1. 現行100件とshadow 100件へ同一versionを適用する
2. BTC適格数、各除外理由、episode/profile coverage、欠測を比較する
3. 少数walletをoutcome-blindで目視照合する
4. schema再実行一致と養分くん側のexample読込確認を行う
5. 問題がなければ次versionを事前固定し、BTC research sample v1を作る

## Existing Snapshot

- current: complete 79 / incomplete 21、79 walletsが成功3日
- shadow: complete 97 / incomplete 3、97 walletsが成功2日
- shadow flags: BOT 27 / MM 4 / farm 6
- research sample: 0
- BTC research selection: `btc-research-selection-v0.1.0-draft`
- BTC handoff schema: `hoihoi-btc-handoff-v0.1`
- contract tests: 36 PASS
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
