# BTC backtest readiness v1

更新: 2026-10-06 JST

## 結論

**現存データはconfirmatory backtestに使用不可。exploratoryのpipeline検証だけ許可する。**

品質一致subsetは44/100 wallet、完結episode 22,973件、BTC 10,125件。数量不一致・連続性誤差は0だが、56 wallet除外によるselection biasが残る。さらにBTC fillの上位5 wallet依存率は72.76%で、独立sample数をfill件数のまま解釈できない。

## Datasetとgrain

- source: Hyperliquid公開fills / TWAP / Fundingと保存済みBTC 5分足
- raw対象期間: 2026-09-02T12:19:21.854000+09:00 〜 2026-10-02T11:42:13.323000+09:00
- BTC canonical fills: 69,708件（TWAP-only 71件）
- BTC取引wallet: 27 / eligible 44
- BTC activity: 7,291 active 5分bucket / 31 JST日
- intended grain: 全連続5分market window。現在はevent table未生成

## Core findings

| finding | evidence | severity | downstream impact |
|---|---:|---|---|
| wallet selection bias | 100中56 wallet除外 | Critical | 母集団のbehavior-performance結論は禁止 |
| wallet concentration | BTC fills上位1 wallet 17.06%、上位5 wallet 72.76% | High | naiveなfill/event数は独立sample数を過大評価 |
| BTC OHLCV outcome不足 | active bucketの60m outcome coverage 55.70% | High | 全期間のreturn/MFE/MAE比較不可 |
| OI / asset context欠測 | historical coverage 0% | Critical | schema準拠feature_ready eventは0 |
| market trade stream欠測 | historical coverage 0% | High | opposite large flow仮説を検証不可 |
| wallet state欠測 | historical coverage 0% | High | leverage/liquidation-distance仮説を検証不可 |
| liquidation evidence不足 | BTC explicit liquidation観測 0件、userEventsなし | High | 損失closeを清算へ読み替え禁止 |

## Outcome coverage

| horizon | covered active buckets | coverage |
|---:|---:|---:|
| 5m | 4,072 | 55.85% |
| 15m | 4,070 | 55.82% |
| 30m | 4,067 | 55.78% |
| 60m | 4,061 | 55.70% |


Fundingはcutoff以前2時間内の観測があるactive bucketで47.09%だが、OIが0%のためOI/Funding/Volume複合仮説は`BLOCKED_OI`とする。

## 時間順split

旧sampling manifestのwallet別splitはBTC episodeがexploratoryへ偏るため、market event-studyには使用しない。最大outcome 60分に合わせ、各境界直前60分をpurgeする。

| split | BTC active 5m buckets | independent JST days | status |
|---|---:|---:|---|
| exploratory | 4,112 | 19 | pipeline検証のみ |
| validation | 1,603 | 7 | 未開封扱い |
| held_out | 1,553 | 7 | 未開封扱い |

境界直前60分のpurgeにより、全coin完結episode 28件、BTC完結episode 9件、BTC active bucket 23件をいずれのsplitにも含めない。境界は`split_manifest.json`へ固定した。ただしdata自体がconfirmatory-readyではないため、分割を作ったことはvalidation開始の許可を意味しない。

## 仮説別status

- `BLOCKED_CORE`: H01。BTC asset context/OIがなくschema準拠eventを作れない。
- `DERIVABLE_NOT_BUILT`: H02、H04、H05。raw transitionから導出可能だが集計table未生成。
- `PARTIAL_EXPLORATORY_ONLY`: H03、H07。保存済みOHLCVの連続範囲でpipeline検証のみ可能。
- `BLOCKED_OI`: H06。historical OI 0%。
- `BLOCKED_NO_TRADES`: H08。BTC trade stream 0%。
- `PARTIAL_PANIC_ONLY`: H09。panic-exit候補は導出可能だがliquidation chainは不可。

詳細は`hypothesis_registry.csv`を正本とする。

## 次の最小実装

1. held-outへ触れず、exploratory期間だけでBTC 5分event aggregatorを実装する。
2. 全windowを保持し、zero-activity windowとsource-gapを区別する。
3. H02/H04/H05のoutcome-free featureを生成する。
4. OHLCVが揃う区間でH07 outcome pipelineだけを検証する。
5. H01/H06/H08/H09の不足seriesはcollector追加要件として明示し、現データで推定しない。

## Source provenance

source fileのSHA-256は`readiness_summary.json`へ保存した。raw wallet addressは成果物へ出力していない。
