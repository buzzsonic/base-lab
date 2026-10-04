# STATUS_SUMMARY

更新: 2026-10-04 JST

## 読み方

通常の「確認して」「状況どう？」では本ファイルを最初に読む。
前回確認commitが分かる場合は、そのcommit以降の養分くん関連差分だけ追加確認する。
`CURRENT_STATUS.md` / `NEXT_TASK.md` / `DECISIONS.md` / 大きなcommit diffは、異常・設計変更・実装作業・詳細監査が必要な時だけ読む。

## Current Phase

BTC event-studyのPHASE 0 data contractを完了。
主目的を個別walletのFOMO/Late/Averaging Down分類から、**養分wallet群の集団行動とその後の市場反応をBTCからevent-studyすること**へ変更した。

VPS runtime packageは実装・CI PASS済みだが、研究の出口とforward data contractを固定するまで本番Shadowは開始しない。

## Key Status

- historical pilot: 不採用
- fixed sample: 100 wallets
- historical再構成で品質条件を満たしたsubset: 44 wallets / completed 22,973 episodes
- subset quality: quantity mismatch 0 / continuity error 0
- v1/v2 forward collector: GitHub schedule間隔不足でFAIL / 凍結
- v3 VPS runtime package: 実装済み、Ubuntu CI / Docker build PASS
- tests: 57 passed
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

## Current Blocker

VPSの有無ではなく、1分/5分market eventのaggregationとpost-event outcome schemaがまだ未固定。

## Next

1. market-event schemaとpost-event outcome schemaを固定
2. 1分/5分window、coverage、future leakage境界を明文化
3. 仮データで期待する最終レポートを先にモック化
4. モックが期待と合うことを確認してからcollector v3へ必要snapshotを追加しVPS Shadow開始

詳細正本: `RESEARCH_DIRECTION.md`

## Last Important Decision

wallet fills/TWAP/Fundingは履歴取得可能。position/leverage/margin/liquidation price/account stateはforward snapshotとしてのみ採用する。BTCのmarket-wide liquidation flowは公式公開APIで直接取得不能とし、proxyで同名保存しない。
VPSは研究目的ではなく安定収集の手段。研究の出口が合うことを確認するまで、本番VPS Shadowを開始しない。
欠落stateの推定・0埋め、wallet差替え、先回りしたinverse-signal結論は禁止。
