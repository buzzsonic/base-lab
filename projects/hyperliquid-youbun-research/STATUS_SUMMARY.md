# STATUS_SUMMARY

更新: 2026-10-05 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

BTC event-studyのPHASE 0 data contract、PHASE 1 event/outcome schema、PHASE 2 synthetic report mockの作成を完了。
主目的を個別walletのFOMO/Late/Averaging Down分類から、**養分wallet群の集団行動とその後の市場反応をBTCからevent-studyすること**へ変更した。

VPS runtime packageは実装・CI PASS済みだが、研究の出口とforward data contractを固定するまで本番Shadowは開始しない。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- subset quality: quantity mismatch 0 / continuity error 0
- v1/v2 forward collector: GitHub schedule間隔不足でFAIL / 凍結
- v3 VPS runtime package: 実装済み、Ubuntu CI / Docker build PASS
- report mock: synthetic 120 events / 480 outcomes / observed market rows 0
- tests: 65 passed
- behavior label v1: 既存PoCとして保持するが主研究単位ではない
- OHLCV本分析 / behavior label本適用 / 500-wallet expansion: HOLD

## New Research Goal

BTCを第一対象に、1分/5分などのmarket window単位で:
- 養分の新規LONG/SHORT数
- LONG/SHORT notional偏り
- entry価格帯の集中
- add / averaging down / pyramiding
- size / leverage / liquidation-distance（取得可能範囲）
- BTC price / volume / OI / Funding / volatility
- large opposite flow / liquidation-like flow（取得可能なら）

を同期し、その後5m / 15m / 30m / 60mのprice reactionを検証する。

「大口が意図的に狙った」とは断定せず、
養分片側集中 → 逆方向large flow → price reversal → panic exit / liquidation-like flow
という観測可能なevent chainの再現性を調べる。

## Current Gate

仮データによる期待レポートmockは作成・表示検証済み。ユーザーが研究の出口と表示項目を確認するまでPHASE 3 collector拡張設計へ進まない。

## Next

1. `design/btc-event-study/report_mock/btc_event_study_report_mock.html`をユーザーが確認
2. 表示項目・粒度・研究の出口が期待と一致するか判定
3. 合意後だけcollector v3拡張設計へ進む
4. collector実装・canary・Shadowは各品質Gateを順に通過してから開始

詳細正本: `RESEARCH_DIRECTION.md`

## Last Important Decision

PHASE 2 mockは固定seedの合成120 event / 480 outcomeだけを使い、実測市場rowは0。coverage不足は欠測のまま表示し、画面上の合成値を相場判断や期待値へ読み替えない。mockのユーザー確認が終わるまでPHASE 3はHOLD。
主分析は連続5分window、一次保存は1分bucket。event featureは`cutoff_ms`以前、outcomeは5/15/30/60分を別namespaceへ物理分離する。optional state/trade/book欠測はcore eventを捨てず該当列だけNULLにする。
wallet fills/TWAP/Fundingは履歴取得可能。position/leverage/margin/liquidation price/account stateはforward snapshotとしてのみ採用する。BTCのmarket-wide liquidation flowは公式公開APIで直接取得不能とし、proxyで同名保存しない。
VPSは研究目的ではなく安定収集の手段。研究の出口が合うことを確認するまで、本番VPS Shadowを開始しない。
欠落stateの推定・0埋め、wallet差替え、先回りしたinverse-signal結論は禁止。
