# STATUS_SUMMARY

更新: 2026-10-05 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分ホイホイ関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / 品質レポート / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Purpose

養分ホイホイは、単に「養分っぽいwallet」を探す仕組みではない。
養分くんが行うBTC event-studyに使える高品質な研究対象walletを、公開データだけで発見・分類・維持し、検証可能なsampleとして引き渡す。

責務は以下に限定する。

- wallet discovery
- BTC取引行動の分類
- BOT / MM / arbitrage / farmの除外
- 観察品質・sample品質の管理
- 養分くんへのversion付きsample handoff

BTCの価格帯・市場局面との結合、その後の価格反応・markout・event-studyは養分くん側の責務とし、養分ホイホイでは分析しない。

## Target Wallet

- BTC Perpを一定頻度で取引し、取引回数が少なすぎない
- 新規建て・追加・部分/全決済を十分に観測できる
- BTCのzero-to-zero episodeと途中のsize変化を再構成できる
- 高値飛び乗り、ナンピン、size急拡大などの行動profileを付与できる
- BOT / MM / arbitrage / farm疑いではない
- 欠測・retention gap・連続性エラーを品質情報として明示できる

具体的な頻度、最低取引回数、最低episode数、観察期間、profile判定閾値は未確定。outcomeや将来価格を見ずに事前定義し、既存cohortでdry-runしてから固定する。

## Current Phase

BTC研究用sample v0.1 dry-runはHOLD。legacyと完全分離した5-wallet・24時間forward canaryを開始した。
観察期間は2026-10-06 00:15:45 JSTから2026-10-07 00:15:45 JST。1件はHoihoi暫定候補、4件はTWAP経路検証専用でsample候補ではない。
7日観察完了前のsample昇格は禁止。1,000-wallet拡大は優先せずHOLDを維持する。

## Key Status

- current discovery pool / selected: 200 / 100
- current cohort: complete 79 / incomplete 21
- current successful observation days: 79 wallets = 3 days, 21 wallets = 0
- shadow cohort: complete 97 / incomplete 3
- shadow successful days: 97 wallets = 2 days, 1 wallet = 1 day, 2 wallets = 0
- shadow flags: BOT 27 / MM 4 / farm 6 / small-alt 11
- current / shadow sample: 0 / 0
- BTC research selection contract: `btc-research-selection-v0.1.0-draft`
- BTC sample handoff contract: `hoihoi-btc-handoff-v0.1`
- contract verification: 36 tests PASS
- BTC dry-run: current 0 / shadow 0 handoff eligible、39 tests PASS
- BTC forward window: `CANARY24H_RUNNING`、51 tests PASS
- live canary: run 37328123994 PASS / raw 14 / BTC 12 / TWAP 0 / gap・cap・sequence欠落・continuity error・same-ms ambiguity 0
- 24h canary initial run: 37330544150 PASS / data `a0d35cca` / successful run 1
- 24h canary namespace: `outputs/btc-research-forward-v1-canary24h/`、config SHA `1afb47b9...5c74f72`
- weekly comparison: run 37172824334 success / data `1b7786e`
- 1,000-wallet expansion: HOLD（当面は非優先）

## Current Blocker

- 全200 walletでTWAP slice evidenceが未取得
- checkpointの同一ms順序がhash順で、current 49 / shadow 40 walletはBTC fill順序を保証できない
- 全200 walletが7成功JST日未達
- high-price-chase用のentry以前BTC市場windowが未結合
- 既存cohortは7成功JST日未達。欠測やretention gapを成功観察として扱えない
- live canaryでTWAP実rowとoverlap重複が0件。API経路は成功したがfirst-seen重複保持のlive証拠は未取得

## Next

1. 2026-10-07 00:15:45 JSTまで5-wallet windowを継続する
2. run間隔・失敗・gap・cap・TWAP実row・overlap重複・同一ms mergeを監査する
3. 24時間Gate通過後だけ7成功JST日用の限定cohortを別namespaceで設計する
4. 7成功JST日後にv0.1を再dry-runする

## Existing Observation Snapshot

dry-runのBTC activity 3条件通過はcurrent 32、shadow 25。再構成品質clearはcurrent 51、shadow 59。観察日・TWAP・市場window以外の暫定Gate通過はcurrent 0、shadow 2だが、最終適格ではない。
small-alt比率はBTC研究適格性の主要KPIではない。

## Last Important Decision

養分ホイホイはBTC event-studyの上流データ品質層へ役割変更する。市場反応は分析せず、wallet discovery / classification / sample quality / sample handoffに集中する。売買・秘密鍵・自動sample採用は行わない。
