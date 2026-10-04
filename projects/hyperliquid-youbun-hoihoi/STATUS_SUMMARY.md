# STATUS_SUMMARY

更新: 2026-10-04 JST

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

BTC研究用sampleの選抜基準とhandoff仕様v0.1 draftを定義済み。現行cohortとshadow cohortの日次観察を継続しながら、次は既存200 walletへのoutcome-blind dry-runを実装する。
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
- weekly comparison: run 37172824334 success / data `1b7786e`
- 1,000-wallet expansion: HOLD（当面は非優先）

## Current Blocker

- 現行registryにBTC専用fills / active days / episode coverageがまだ保存されていない
- v0.1はdry-run前draftであり、実データでの適格数・除外理由・profile missingnessは未検証
- high-price-chase判定に必要なentry以前のBTC市場windowはhandoff前に用意する必要がある
- 既存cohortは7成功JST日未達。欠測やretention gapを成功観察として扱えない

## Next

1. 現行100件とshadow 100件からBTC fillsを抽出し、zero-to-zero episodeとcoverageを再構成する
2. v0.1 Gateをdry-runし、適格数・除外理由・profile missingnessをcohort別に比較する
3. TRUE / FALSE / UNAVAILABLEを層別にoutcome-blind目視照合する
4. 養分くん側でexample handoffのschema・hash・重複検証を行う
5. 品質確認後に新versionを事前固定し、BTC research sample v1を作成する

## Existing Observation Snapshot

shadowはcurrent比でcomplete history +18、BOT suspected -11、MM suspected -8だが、これはBTC研究適格性の確定評価ではない。
small-alt比率は新目的の主要KPIから外し、BTC取引coverageと行動再構成可能性を優先する。

## Last Important Decision

養分ホイホイはBTC event-studyの上流データ品質層へ役割変更する。市場反応は分析せず、wallet discovery / classification / sample quality / sample handoffに集中する。売買・秘密鍵・自動sample採用は行わない。
