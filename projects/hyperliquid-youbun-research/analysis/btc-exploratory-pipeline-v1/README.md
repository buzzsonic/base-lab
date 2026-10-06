# BTC exploratory pipeline v1

## 判定

この成果物はexploratory期間だけを使った**pipeline検証**であり、仮説の成績評価ではない。validation / held-outの処理件数は0。

- continuous 5m event rows: 5,318
- activity / zero activity: 4,112 / 1,206
- BTC candle READY: 1,714
- prior 60m READY: 1,703
- core feature READY: 0（historical asset contextが0%のため）
- new-entry feature rows: 662
- averaging-down feature rows: 251
- past-20 size baseline ready rows: 2,593
- H07 price outcome READY: {'5': 1714, '15': 1714, '30': 1714, '60': 1714}

`events_exploratory.csv`にfuture return / MFE / MAEを置かず、`outcomes_exploratory.csv`へ物理分離した。5分足しかないためtime-to-high/lowは5分解像度であり、PHASE 1の1分正規schemaとは区別したexploratory schemaを使う。

OI、asset context、market trades、wallet state、明示的liquidation eventは推定せずblockを維持する。effect size、勝率、p値、逆指標性、閾値採否は計算していない。
