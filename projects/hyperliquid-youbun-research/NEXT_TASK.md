# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分くん関連commit差分だけ確認する。
`CURRENT_STATUS.md` / `DECISIONS.md` / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

研究順序を変更する。

主目的は個別walletの行動ラベル分類ではなく、**養分wallet群の集団行動と、その後の市場反応をBTCからevent-studyすること**。

レポート作成を先行しない。現在取得済みの実データから仮説を立て、backtest、条件修正、再backtest、別期間・別sampleのout-of-sample検証を行い、再現した仮説だけを最終レポートへ載せる。

詳細契約は `RESEARCH_DIRECTION.md` を正本とする。

VPS runtime package自体は実装・CI PASS済みだが、収集契約を再設計するまで本番VPS Shadowは開始しない。

## PHASE 0: BTC event-study data contract【完了】

Codexは既存collector/APIで取得可能な項目を棚卸しし、以下を「取得可能 / forwardなら取得可能 / 取得不能」に分類する。

### 養分群
- fills / TWAP / Funding
- current position size
- side
- entry price
- configured leverage
- margin mode
- liquidation price
- account equity / margin usage
- effective leverage proxy
- add / reduce / close
- realized-loss exit

### BTC市場
- price / OHLCV
- volume
- OI / OI change
- Funding
- volatility
- aggressive buy/sell flow
- large trade flow
- order-book imbalance
- liquidation flow

成果物:
- `design/btc-event-study/data_contract.md`
- `design/btc-event-study/field_matrix.csv`

欠損を推定で埋めない。APIで任意の過去stateを復元できないものはforward snapshot対象にする。

完了内容:
- 28項目を`取得可能 / forwardなら取得可能 / 取得不能`へ分類
- position/leverage/margin/liquidation price/account stateをforward snapshotへ限定
- BTC market-wide liquidation flowは公式公開APIで直接取得不能と確定

## PHASE 1: event schemaとaggregation設計【完了】

1分/5分windowを候補に、BTCについて最低限以下を定義する。

- active_youbun_wallets
- new_long_wallets / new_short_wallets
- long_notional / short_notional
- long_short_imbalance
- entry_price_mean / median / concentration
- distance_from_local_high_low
- add / averaging_down / pyramiding counts
- exit / realized_loss_exit intensity
- leverage distribution（取得可能範囲）
- liquidation-distance distribution（取得可能範囲）
- BTC return / volume / OI / Funding / volatility
- large opposite flow（取得可能なら）

future leakageを避け、entry時点で利用可能な特徴とpost-event outcomeを物理的に分離する。

成果物:
- `design/btc-event-study/event_schema.md`
- `design/btc-event-study/outcome_schema.md`

完了内容:
- 1分raw bucket、連続5分event window、5/15/30/60分outcomeを固定
- wallet transition、crowd、entry concentration、market、optional state/flowの式を定義
- event featureとpost-event outcomeを別namespaceへ物理分離
- Hoihoi handoff v0.1の受入境界とcoverage/UNAVAILABLE契約を定義

## PHASE 2: synthetic report mock【完了・参考UIへ格下げ】

データ収集前に、最終的に欲しいレポート形式を仮データで作る。

最低限:
- 養分LONG/SHORT集中の分布
- BTC価格位置とentry集中
- leverage/size分布（取れる範囲）
- crowd concentration percentile
- 条件別5m/15m/30m/60m future return
- downside/upside probability
- MFE/MAE
- opposite large flow occurrence
- panic exit / liquidation-like flow occurrence

レポートには、例えば
「BTC上昇後・養分LONG比率高・高値近辺entry集中・OI増加・高値更新失敗」
のような複合eventを表示できる形にする。

成果物:
- `design/btc-event-study/report_mock/`

完了内容:
- 固定seedの合成120 event / 480 outcomeで再生成可能なmock datasetを作成
- LONG/SHORT集中、entry集中、size/leverage（coverage範囲内）、5/15/30/60分return、逆行率、MFE/MAE、opposite flow、panic exit、明示的liquidationを表示
- optional coverage不足を0埋めせず欠測表示
- offline単体HTMLを生成し、ブラウザで全体レイアウトとchart/table描画を確認
- 実測市場row 0、売買判断・期待収益・逆指標性の結論なしを画面上部と末尾に明記

synthetic mockは参考UIとして保持する。仮説作成、閾値選択、研究判断、採否には使わず、ユーザー確認を次工程の開始条件にしない。

## PHASE 3: 実データbacktest readiness監査【完了】

現在取得済みの実データについて、優先仮説ごとに次を定量化する。

- usable event / episode数
- 観測期間と独立なJST日数
- wallet数、wallet集中度、除外率、sampling bias
- exploratory / validation / held-outへ時間順に分割できるか
- BTC OHLCV / Volume / Funding / OI coverage
- entry concentration / local high-low / averaging down / size changeの算出可否
- 5m / 15m / 30m / 60m return、MFE / MAEの算出可否
- opposite flow / panic exit / explicit liquidation evidenceのcoverage

最初の成果物:
- `analysis/btc-backtest-v1/data_readiness.md`
- `analysis/btc-backtest-v1/hypothesis_registry.csv`
- `analysis/btc-backtest-v1/split_manifest.json`

停止条件:
- outcomeにfuture leakageがある
- event/outcome joinが一意でない
- coverage不足を0埋めしないと成立しない
- historical subsetの56%除外biasを代表sampleとして扱っている
- validation / held-outを見て閾値を調整している

完了内容:
- 品質一致44 wallet・完結22,973 episodeを監査し、BTC完結10,125 episode、canonical fills 69,708件を確認
- 100 wallet中56 wallet除外、BTC fills上位5 wallet依存72.76%を重大biasとして固定
- active 5分bucket 7,291件に対し60分outcome coverage 55.70%、historical OI / asset context / trades / wallet stateは0%
- 9仮説をversion付きregistryへ登録し、実装可能・部分探索のみ・blockを分離
- 時間順exploratory / validation / held-outと境界前60分purgeを固定
- 判定は`NOT_READY_FOR_CONFIRMATORY_BACKTEST`。仮説の成績・採否はまだ出していない

## PHASE 4: exploratory pipeline構築【次】

held-outへ触れず、exploratory期間だけで以下を実装・検証する。

1. 全連続5分windowを保持するBTC event aggregator
2. zero activityとsource gapを区別するcoverage列
3. H02 entry価格帯集中、H04 averaging down、H05 size急拡大のoutcome-free feature
4. OHLCV完備windowだけに対するH07の5/15/30/60分return・MFE・MAE
5. event/outcomeの物理分離、一意join、future leakageなしのテスト

この工程はpipeline検証であり、effect size、勝率、逆指標性、仮説採否を結論しない。H01/H06/H08/H09は不足seriesを推定せずblockを維持する。

## PHASE 4B: 仮説別exploratory backtest【coverage Gate通過後】

BTCで次の順に検証する。

1. 養分LONG/SHORT集中
2. entry価格帯の集中
3. 高値/安値付近での飛び乗り
4. averaging down
5. size急拡大
6. OI / Funding / Volumeとの複合条件
7. その後5m / 15m / 30m / 60m return、MFE / MAE
8. 反対方向flow、panic exit / liquidation-like flow

各仮説はID・version・必要field・閾値候補・regime・主metric・最低sample・欠測条件を事前登録する。閾値修正は元versionを上書きせず、新versionとしてexploratory内で再backtestする。

## PHASE 5: validation / held-out再現性検証

- exploratoryで固定した条件を変更しない
- sample数と独立日数を併記する
- bull / bear / range、高vol / 低volなど事前定義regime別に確認する
- averageだけでなくmedian、分布、confidence interval、downside/upside probability、MFE/MAEを確認する
- overlapping windowとwallet内相関を考慮する
- 複数仮説・閾値探索による偶然の当たりを考慮する
- 別期間・別sampleで方向と有意義なeffect sizeが再現しない仮説は棄却する

validation / held-outを見て条件を変えた場合、その結果は探索へ格下げし、新しい未使用期間または未使用sampleを必要とする。

## PHASE 6: collector追加設計

実データreadiness監査で重要仮説の必要fieldが不足すると確定した場合だけ、既存Ubuntu VPS + Docker + systemd timer packageへforward snapshotを追加する。収集自体を目的化しない。

## PHASE 7: 最終レポート

再現性Gateを通過した仮説だけを掲載する。有意義な結果が出ない仮説は棄却し、空欄を埋めるための物語や相関は載せない。

## 最終的な研究問い

1. 養分walletはBTCのどの局面で片側へ偏るか
2. その時のsize/leverage/add行動はどうか
3. crowd集中後5m/15m/30m/60mの価格反応はどうか
4. OI/Funding/高値更新失敗等との複合条件で反転確率は高まるか
5. crowd集中→逆方向large flow→panic exit/liquidation-like flowというevent chainが再現するか

「大口が意図的に狙った」とは断定せず、観測可能なevent chainと条件付き確率を検証する。

## HOLD

readiness監査で必要性を確認し、個別の収集品質Gateを通過するまで:
- VPS本番Shadow開始
- behavior label本適用
- 500-wallet expansion

再現性Gate通過まで:
- inverse-signal結論
- 最終レポート作成

は禁止。
