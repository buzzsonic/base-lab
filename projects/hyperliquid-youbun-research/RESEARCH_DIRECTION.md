# RESEARCH_DIRECTION

更新: 2026-10-04 JST

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

## 期待する最終レポート例

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
- 個別walletラベルは市場event説明の補助に使う
- まずBTCで設計を成立させ、他coinへ広げる

## VPSとの関係

VPSはcollectorを安定稼働させる手段であり、研究目的ではない。

VPS投入前に、上記event-studyに必要なforward data contractを固定する。
既存v3 scheduler packageは再利用可能だが、収集項目が確定するまで本番Shadowを開始しない。
