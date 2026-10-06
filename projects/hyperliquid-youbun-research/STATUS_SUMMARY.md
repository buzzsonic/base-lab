# STATUS_SUMMARY

更新: 2026-10-06 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

BTC event-studyのdata contractとevent/outcome schemaは固定済み。synthetic report mockも作成済みだが、今後はレポート作成を先行しない。

exploratory split上のpipeline検証を完了した。連続5分eventとoutcomeの物理分離はPASSしたが、historical BTC asset contextが0%でcore feature READYも0件。仮説成績へ進まず、必要なforward core seriesのcollector追加設計へ移る。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- subset quality: quantity mismatch 0 / continuity error 0
- v1/v2 forward collector: GitHub schedule間隔不足でFAIL / 凍結
- v3 VPS runtime package: 実装済み、Ubuntu CI / Docker build PASS
- report mock: 参考UIとして保持。synthetic 120 events / 480 outcomes / observed market rows 0。研究判断には不使用
- tests: 79 passed
- behavior label v1: 既存PoCとして保持するが主研究単位ではない
- 現在の実データ: 品質条件を満たす44 wallets / 22,973 completed episodes。ただし56%除外によるsampling biasがあり、探索用途に限定
- behavior label本適用 / 500-wallet expansion / inverse-signal結論: HOLD
- BTC readiness: 10,125 completed episodes / 69,708 canonical fills / 7,291 active 5m buckets
- bias: 56/100 wallet除外、BTC fill上位5 wallet依存72.76%
- outcome coverage: 5m 55.85% / 60m 55.70%。historical OI・asset context・trades・wallet stateは0%
- decision: `NOT_READY_FOR_CONFIRMATORY_BACKTEST` / exploratoryはpipeline検証だけ
- exploratory pipeline: 5,318 continuous windows / activity 4,112 / zero activity 1,206
- outcome-free features: H02 662 windows / H04 251 / H05 baseline-ready 2,593
- H07 price outcome READY: 5/15/30/60m 各1,714 windows（5分足解像度）
- core feature READY: 0。PHASE 4B hypothesis performanceはHOLD

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

## Adoption Gate

単発の相関、同一期間だけの好結果、少数sample、特定regimeだけの結果は採用しない。sample数・期間・regime別の安定性を示し、固定した条件が別期間・別sampleのout-of-sampleでも同方向に再現した仮説だけを採用する。有意義な再現性がない仮説は棄却する。

## Next

1. BTC asset context（mark / OI / Funding）を最小coreとしてforward収集設計へ追加
2. BTC 1分candleとcollector health / gap manifestを同じ時刻契約で保存
3. BTC tradesはH08用optional groupとして分離設計
4. wallet state、BBO/L2、liquidation eventは一括実装せず後段optional拡張にする
5. core coverage Gateを通過するまでPHASE 4Bの仮説成績評価を開始しない

詳細正本: `RESEARCH_DIRECTION.md`

## Last Important Decision

synthetic report mockは参考UIとして残すが、仮説作成・閾値選択・採否・相場判断には使わない。研究は実データのPDCAを先行し、再現性が確認できた結果だけを最終レポートへ載せる。
主分析は連続5分window、一次保存は1分bucket。event featureは`cutoff_ms`以前、outcomeは5/15/30/60分を別namespaceへ物理分離する。optional state/trade/book欠測はcore eventを捨てず該当列だけNULLにする。
wallet fills/TWAP/Fundingは履歴取得可能。position/leverage/margin/liquidation price/account stateはforward snapshotとしてのみ採用する。BTCのmarket-wide liquidation flowは公式公開APIで直接取得不能とし、proxyで同名保存しない。
VPSは研究目的ではなく不足データを安定収集する手段。readiness監査で必要性を確認し、canary品質Gateを通過するまで本番VPS Shadowを開始しない。
欠落stateの推定・0埋め、wallet差替え、先回りしたinverse-signal結論は禁止。
