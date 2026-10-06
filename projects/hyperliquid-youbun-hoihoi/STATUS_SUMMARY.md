# STATUS_SUMMARY

更新: 2026-10-07 JST

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

BTC研究用sample v0.1 dry-runはHOLD。legacyと完全分離した5-wallet・24時間forward canaryはGate FAILで終了し、workflowを`disabled_manually`へ停止した。
TWAP・overlap・順序・position chain経路は実証したが、GitHub schedule欠測により連続市場windowを確保できなかった。
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
- BTC forward window: `CANARY24H_GATE_FAIL_SCHEDULER`、52 tests PASS
- live canary: run 37328123994 PASS / raw 14 / BTC 12 / TWAP 0 / gap・cap・sequence欠落・continuity error・same-ms ambiguity 0
- 24h canary: collection run 5 / expected 73、最大gap 413.8分、終端gap 367.0分
- 24h raw: fills 800 / TWAP 2,499 / overlap duplicate 180 / BTC position row 46
- 24h quality: endpoint failure・cap・source gap・source order failure・same-ms ambiguity・continuity errorは全て0
- BTC 5m coverage: 77 / 288 = 26.7%（Gate 95%未達）
- Hoihoi暫定候補: fills 3 / TWAP 0 / BTC row 0
- 24h canary namespace: `outputs/btc-research-forward-v1-canary24h/`、config SHA `1afb47b9...5c74f72`
- weekly comparison: run 37172824334 success / data `1b7786e`
- 1,000-wallet expansion: HOLD（当面は非優先）

## Current Blocker

- 全200 walletでTWAP slice evidenceが未取得
- checkpointの同一ms順序がhash順で、current 49 / shadow 40 walletはBTC fill順序を保証できない
- 全200 walletが7成功JST日未達
- high-price-chase用のentry以前BTC市場windowが未結合
- 既存cohortは7成功JST日未達。欠測やretention gapを成功観察として扱えない
- GitHub scheduleが20分cadenceを配信できず、最大413.8分gap。市場window coverage 26.7%
- Hoihoi暫定候補は24時間BTC活動0で、短期活動性の証拠不足

## Next

1. GitHub scheduleを使わないsingle-flight外部timerをHoihoi用に設計する
2. 開始直前の公開BTC Tradesで活動を確認した少数walletをoutcome-freeに固定する
3. 新namespaceで24時間canaryを再実行し、run gapとBTC 5m coverage Gateを通す
4. Gate通過後だけ7成功JST日用の限定cohortを設計する
5. 7成功JST日後にv0.1を再dry-runする

## Existing Observation Snapshot

dry-runのBTC activity 3条件通過はcurrent 32、shadow 25。再構成品質clearはcurrent 51、shadow 59。観察日・TWAP・市場window以外の暫定Gate通過はcurrent 0、shadow 2だが、最終適格ではない。
small-alt比率はBTC研究適格性の主要KPIではない。

## Last Important Decision

養分ホイホイはBTC event-studyの上流データ品質層へ役割変更する。市場反応は分析せず、wallet discovery / classification / sample quality / sample handoffに集中する。売買・秘密鍵・自動sample採用は行わない。
