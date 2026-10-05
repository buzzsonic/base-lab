# RESEARCH_DIRECTION

更新: 2026-10-06 JST

## 目的

養分くんの主目的を、個々のwalletへFOMO/Late/Averaging Down等のラベルを付けることから、
**養分wallet群の集団行動が市場価格へどう反映され、その後どの方向へ動きやすいかを検証すること**へ変更する。

個別行動ラベルは補助説明変数として残すが、研究の主単位にはしない。

## 最初の対象

BTCを第一対象にする。

研究単位はwallet単位ではなく、1分/5分などの**market event window**とする。

## 各windowで集計したい養分群側の特徴

最低限:
- active youbun wallet count
- new LONG wallet count / new SHORT wallet count
- LONG notional / SHORT notional
- LONG/SHORT imbalance
- weighted mean / median entry price
- entry price concentration
- local high / lowからentryまでの距離
- add / averaging down wallet count
- profit pyramiding wallet count
- position increase intensity
- exit / panic-close intensity
- realized loss exit count
- possible liquidation / forced-exit evidence where observable

forward collectionで取得可能なら:
- wallet current position size
- margin mode
- configured leverage
- liquidation price
- account equity / margin usage
- effective leverage proxy

取得できない過去stateを推定で埋めない。

## 市場側の特徴

最低限:
- BTC price / return
- volume
- OI / OI change
- Funding
- volatility
- local high / low / breakout state

取得可能なら:
- aggressive buy/sell flow
- large trade flow
- order-book imbalance
- liquidation flow

## 主な問い

1. 養分walletはBTCのどの価格位置・値動きの後でLONG/SHORTへ偏りやすいか。
2. その時のposition size / leverage / add行動にはどんな共通点があるか。
3. 養分群の片側集中が一定閾値を超えた後、5m / 15m / 30m / 60mで価格はどう動くか。
4. 養分LONG集中 + OI増加 + 高値更新失敗など、複合条件で反転確率や期待値は高まるか。
5. 養分集中後に逆方向のlarge flowが出現し、その後panic exit / liquidation cascadeへ繋がるパターンが再現するか。

## 「大口に狙われる」の扱い

意図は直接観測できないため、"大口が狙った"とは断定しない。

検証対象は以下の観測可能な順序:

1. 養分wallet群が片側へ集中
2. 価格が伸びにくくなる / OIだけ増える等の状態
3. 逆方向のlarge aggressive flowが出現
4. 価格が逆行
5. 養分wallet群の損切り・強制退出・清算相当flowが増える
6. さらに価格が進む

このevent chainの頻度・条件付き確率・その後returnを検証する。

## 研究PDCA

レポートの形から研究条件を逆算しない。以下の順序を正本とする。

1. 現在取得できている実データだけから、検証可能な仮説をversion付きで登録する。
2. exploratory期間で仮説ごとにbacktestする。
3. 結果を見て条件・閾値・市場regimeを修正する場合は、元定義を上書きせず新versionにする。
4. 同じexploratory期間で再backtestし、sample数・effect size・不確実性・欠測・複数検定の影響を確認する。
5. 固定した条件をvalidation、最後に別期間・別sampleのheld-outで評価する。
6. 方向・大きさ・発生率がregimeを跨いで再現した仮説だけを採用する。再現しない仮説は棄却し、最終レポートへ載せない。

同じdataを見ながら閾値を変え続けた結果をout-of-sampleと呼ばない。validation / held-outの結果を見て条件を変更した場合、その結果は探索へ格下げし、新しい未使用期間または未使用sampleを必要とする。

## 優先仮説

BTCを対象に、以下を順に検証する。

- 養分LONG/SHORTの集中
- entry価格帯の集中
- local high / low付近での飛び乗り
- averaging down
- position sizeの急拡大
- OI / Funding / Volumeとの複合条件
- その後5m / 15m / 30m / 60mのreturn
- MFE / MAE
- 反対方向flow
- panic exit / liquidation-like flow

必要seriesのcoverageが不足する仮説はFALSEにせず`UNAVAILABLE`とし、取得可能になるまで保留する。

## 仮説の採用条件

- event数と独立な日数を併記し、少数sampleの好結果を採用しない。
- bull / bear / range、高vol / 低volなど事前定義したregime別に方向と大きさを確認する。
- exploratoryで見つけた閾値をvalidation / held-outでは固定する。
- averageだけでなくmedian、分布、confidence interval、downside/upside probability、MFE/MAEを確認する。
- overlapping windowや同一walletの連続eventによる擬似的なsample増加を補正する。
- 複数仮説・閾値探索による偶然の当たりを考慮する。
- 別期間・別sampleで同方向に再現しない結果、有意義なeffect sizeがない結果は棄却する。

## 最終レポート

最終レポートは研究の開始点ではなく、再現性確認後の成果物とする。synthetic report mockは参考UIとしてのみ保持し、仮説作成、閾値選択、採否、相場判断には使わない。

以下は採用済み仮説を表示する場合の例であり、先に埋めるべき構成ではない。

BTCについて、単なるwallet分類ではなく、以下の形を目標にする。

例:
- BTCが直近1hで+X%以上上昇
- 養分walletのLONG比率がY%以上
- 5分以内の新規LONG wallet数がN以上
- entry中央値がlocal highからZ%以内
- OI増加、価格は高値更新失敗

この条件の後:
- 5m / 15m / 30m / 60m return
- downside probability
- MFE / MAE
- liquidation / panic-exit発生率
- large opposite flow発生率

を探索/validation/held-outに分けて報告する。

## 研究上の原則

- future leakage禁止
- 欠損stateを推定・0埋めしない
- 養分walletだから逆張りすればよい、という結論を先に置かない
- 閾値はexploratoryで発見し、validationで確認し、held-outで最終評価する
- report作成を先行せず、再現性を通過した結果だけを最終reportへ載せる
- 有意義な結果が出ない仮説は棄却し、無理に物語を作らない
- 個別walletラベルは市場event説明の補助に使う
- まずBTCで設計を成立させ、他coinへ広げる

## VPSとの関係

VPSはcollectorを安定稼働させる手段であり、研究目的ではない。

VPS投入前に、上記event-studyに必要なforward data contractを固定する。
既存v3 scheduler packageは再利用可能だが、収集項目が確定するまで本番Shadowを開始しない。
