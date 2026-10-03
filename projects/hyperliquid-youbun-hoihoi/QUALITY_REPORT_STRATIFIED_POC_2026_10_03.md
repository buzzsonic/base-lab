# 養分ホイホイ 層化再PoC検証 2026-10-03

## 結論

- 隔離した200→100件の再PoCは成功した。既存registryは変更していない。
- 新100件は、現行100件に対して履歴不完全、小型アルト不足、BOT/MM偏重の全項目で改善した。
- ただし成功観察日は完全取得98件が1日、欠損2件が0日であり、7日・7 JST日分のpromotion gateは未達。現行100件を直ちに置換せず、新cohortの継続観察を実装して比較する。
- 1,000-wallet拡大はHOLDを維持する。

## 実行証拠

- [public Trades収集 run 37116093295](https://github.com/buzzsonic/base-lab/actions/runs/37116093295): success、5分32秒。22/22市場、ユニーク767 wallet、missing market・reconnect・malformed message・collector errorはいずれも0。
- [既存100件の観察 run 37116402104](https://github.com/buzzsonic/base-lab/actions/runs/37116402104): success、8分32秒。data branchへの保存も成功。
- [snapshot run 37116871931](https://github.com/buzzsonic/base-lab/actions/runs/37116871931): success。
- [隔離再PoC run 37116104107](https://github.com/buzzsonic/base-lab/actions/runs/37116104107): success、59分23秒。artifact `youbun-hoihoi-poc-preview-37116104107-1`を解析した。
- PR #25でdata branch pushを最大3回、fetch/rebase後に再試行するよう修正。今回の収集・観察保存はともに成功し、force pushは使用していない。

## 現行100件と新100件の比較

| 指標 | 現行100件 | 新100件 | 判定 |
|---|---:|---:|---|
| 履歴完全 | 79 | 98 | 改善 |
| 履歴不完全 | 21 | 2 | 改善 |
| 2,000件応答に1回以上到達 | 参考値: 旧Issue #8で63 | 24 | 指標定義が異なるため参考比較 |
| BOT疑い | 39 | 29 | 改善 |
| MM疑い | 12 | 4 | 改善 |
| farm疑い | 1 | 6 | 増加、要継続確認 |
| arbitrage疑い | 1 | 0 | 参考値 |
| inactive | 15 | 15 | 同じ |
| 高頻度 / 中頻度 / 低頻度 | 48 / 30 / 22 | 42 / 36 / 22 | 高頻度偏重が緩和 |
| BTC/ETH / alt / small-alt / unknown | 37 / 48 / 0 / 15 | 31 / 45 / 9 / 15 | small-alt不足が改善 |
| leaderboard / public Trades | 63 / 37 | 60 / 40 | やや均衡化 |
| 現行100件との重複 | - | 42 | 58件が入替候補 |
| 重複wallet | 0 | 0 | 問題なし |

注: 現行の「履歴不完全21」は10,000件retentionを含む完全性判定、新cohortの「2,000件応答到達24」は分割取得中にcap応答があったwallet数であり、同一指標ではない。新cohortは分割後98件が完全取得できた。

## 時間帯coverage

保存済み収集は10 run。JST 4時間帯をすべて最低1回取得した。

| JST時間帯 | run数 |
|---|---:|
| 00–05 | 1 |
| 06–11 | 1 |
| 12–17 | 1 |
| 18–23 | 7 |

4帯到達は再PoC実行条件として満たしたが、18–23時へ偏っている。均等coverageや曜日差を証明したとは扱わない。

## 20件の層別レビュー

新100件からMM疑い4、farm疑い6、BOTのみ5、small-altかつflagなし3、その他flagなし2をwallet文字列順で決定的に抽出した。

| # | wallet | 区分 | 30日perp fills | fills/active day | median間隔秒 | maker比率 | median size | 銘柄数 | profile | 判定 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | `0x103e9d15f8a102ef9333ad8b66ffe25b0db448a4` | BOT+MM | 1,292 | 258.4 | 42.1 | 0.973 | 208.47 | 1 | alt | 閾値整合、単一銘柄のためMM確定不可 |
| 2 | `0x2b65629ece148099d3020fa641af7023e2da64e8` | BOT+MM | 4,713 | 314.2 | 64.6 | 0.995 | 861.46 | 1 | BTC/ETH | 閾値整合、単一銘柄のためMM確定不可 |
| 3 | `0x9e0653ff7b7f600dcf2cdcdbad15863fc5c7693b` | BOT+MM | 730 | 81.1 | 0.6 | 0.921 | 99.78 | 8 | alt | 自動執行疑いは強い |
| 4 | `0xe86b057f5eb764c9738d6b0d38170befd0723664` | BOT+MM | 10,984 | 3,661.3 | 7.1 | 1.000 | 1,887.96 | 48 | alt | 強い疑い、履歴不完全 |
| 5 | `0x31ca8395cf837de08b24da3f660e77761dfb974b` | BOT+farm | 7,355 | 7,355.0 | 0.4 | 0.282 | 19.05 | 173 | alt | 強い疑い |
| 6 | `0x3508a8d282b283e47f3ed184a423ce89f05904d2` | BOT+farm | 2,115 | 423.0 | 8.9 | 0.000 | 10.14 | 129 | small-alt | 強い疑い |
| 7 | `0x4736a38ef97bc31c9f7c97e6bd47d35868386a09` | farm | 1,165 | 53.0 | 61.6 | 0.005 | 17.79 | 29 | alt | 閾値整合、farm確定不可 |
| 8 | `0xc9c45e0714d735ceb3dd5b39fd40a868431b900d` | farm | 2,065 | 66.6 | 81.9 | 0.662 | 13.16 | 93 | small-alt | 閾値整合、farm確定不可 |
| 9 | `0xced291e04e66eaf884f625ad104e987a9162296a` | farm | 1,394 | 46.5 | 68.8 | 0.796 | 48.78 | 51 | small-alt | 閾値整合、farm確定不可 |
| 10 | `0xd005a79ce77f30bcd1138b2d837507f88d168d81` | BOT+farm | 547 | 18.9 | 3.7 | 0.452 | 13.69 | 92 | small-alt | 自動執行疑いは強い |
| 11–15 | BOTのみ5件 | BOT | 628–8,593 | 65.4–729.1 | 0.5–59.5 | 0.001–0.571 | 90.13–7,049.28 | 1–16 | alt/BTC・ETH | 全件BOT閾値と整合 |
| 16–18 | flagなしsmall-alt 3件 | OBSERVING | 40–202 | 8.0–95.0 | 30.7–23,911.1 | 0–0.895 | 71.68–231.89 | 2–49 | small-alt | 除外根拠なし |
| 19–20 | その他flagなし2件 | OBSERVING | 12–210 | 12.0–23.3 | 0–4.2 | 0–0.571 | 134.67–1,463.95 | 1–18 | alt | 除外根拠なし |

レビュー上、実装された閾値との不一致は0/20。ただし公開約定の集計だけではMM/farm戦略を確定できない。ラベル名どおり疑いとして扱い、通常sampleから保守的に除外する。特に単一銘柄・高maker比率の2件は、MMではなく執行アルゴの可能性がある。

## 次の判断

1. 新100件を別cohortとして永続化し、既存100件を壊さず7 JST日分観察する。
2. 7日後に履歴完全性、flag率、small-alt比率、欠測、API所要時間を再比較する。
3. farm疑い6件と単一銘柄MM疑い2件を重点レビューする。
4. 新cohortがgateを通過した場合だけ、現行cohortとの置換または統合を決める。
5. 1,000-wallet拡大はその後に再判定する。
