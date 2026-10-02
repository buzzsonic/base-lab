# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. 完了済みゲート

- episode再構成: 61/61 PASS
- 層別目視: 20/20 PASS
- 会計照合: 61/61 PASS
- 5分市場series coverage: 完了
- past-only特徴量: PARTIAL 24episodeへ付与済み
- future leakage test: PASS
- historical mark / OI: unavailableのためNULL維持
- 26 tests PASS

---

## 1. 行動ラベル定義の事前登録【最優先】

目的:
24episodeの実データを見てから都合よく閾値を変更することを防ぎ、再現可能な行動分類ルールを先に固定する。

今回は「定義・実装契約・テスト」まで。
24episodeへの分類結果はpipeline確認に限定し、成績評価や逆指標性の結論を出さない。

成果物:
`labels/preregistered-v1/`

最低限:
- `README.md`
- `label_definitions.md`
- `label_config.json`
- `label_schema.json`
- 単体test
- 24episodeへのdry-run結果

---

## 2. v1で事前登録するラベル

### FOMO_LONG / FOMO_SHORT

基本概念:
短時間にすでに大きく進んだ方向へ、出来高拡大を伴って遅れてentryした行動。

使用可能series:
- return_5m
- return_15m
- return_1h
- volume_ratio
- range_position
- breakout_distance
- BTC relative
- side

必要条件を明文化:
- direction-adjusted returnが一定以上
- volume拡大
- local range端に近い
- entry方向と直前moveが同方向

閾値はconfigへ固定する。
閾値の根拠は「PoC初期値」として明記し、24episodeを見てから変更しない。

### LATE_LONG / LATE_SHORT

基本概念:
方向自体は継続しているが、entry時点ですでにmoveの後半・range端・breakout後に位置するentry。

FOMOとの違い:
- FOMOは急加速＋出来高拡大を重視
- Lateはmove進行度・位置を重視

必要条件:
- direction-adjusted return
- range_position / local high-low距離
- breakout_distance
- side整合

FOMOとの重複可否を明記する。

### AVERAGING_DOWN_LONG / AVERAGING_DOWN_SHORT

基本概念:
既存ポジションが含み損方向へ動いた後、同方向へ追加する行動。

これはmarket featureではなくepisode内fill sequenceを主に使う。

必要条件:
- 同一episode内で追加fillあり
- 追加前から既存positionあり
- 追加時価格が、Longなら平均entryより不利な下側、Shortなら不利な上側
- 追加量が極小ノイズでない

保存:
- adds_count
- adverse_add_count
- adverse_add_size_ratio
- worst_adverse_add_distance

Profit pyramidingと区別する。

### PROFIT_PYRAMIDING_LONG / SHORT

基本概念:
含み益方向へ進んだ後に同方向へ追加。

AVERAGING_DOWNと対称ルールで定義する。
将来比較用に必ず分けて保存する。

### REVENGE_CANDIDATE

基本概念:
損失episode終了後、短時間で次episodeへ入り、通常よりサイズまたはentry頻度が増える候補。

重要:
単一episodeでは確定できない。
wallet内episode sequenceを使用する。

必要条件:
- 直前episodeがloss
- 次entryまでのelapsed time
- 前episode比のsize ratio
- 同一coin / 反対side / 同方向のどれかを補助情報として保存

v1では「候補ラベル」とし、心理状態を断定しない。

---

## 3. 今回まだ定義しないラベル

以下はseries不足のためv1対象外。

- CROWDING
  - historical OI不足
- TRAPPED
  - historical margin / liquidation state不足
- LIQUIDATION_BEHAVIOR
  - liquidation event標本不足
- 「逆指標」
  - outcome評価であり行動ラベルではない

---

## 4. Long / Short正規化

全ラベルはdirection-adjusted metricを使える設計にする。

例:
- Long: price riseをpositive
- Short: price fallをpositive

Long/Shortで別実装を乱立させず、共通関数＋side signで正規化する。

ただし出力ラベル名はLONG / SHORTを明示する。

---

## 5. 重複ラベル方針

1 episodeに複数ラベルを許可する。

例:
- FOMO_LONG + LATE_LONG
- AVERAGING_DOWN_LONG + FOMO_LONG

排他的分類にしない。

各ラベルについて:
- boolean
- score
- triggered_rules
- missing_required_features
を保存する。

必要series不足時はFALSEにせず `UNAVAILABLE` を持てるschemaにする。

---

## 6. 閾値の事前固定

`label_config.json` にすべての閾値を保存する。

必須:
- config_version
- created_at
- rationale
- threshold値
- required_features
- minimum_sample_note

24episodeの分類結果を見た後にv1閾値を書き換えない。

変更が必要なら `v2` として別versionを作る。

---

## 7. 24episode dry-run

事前登録後にのみ24episodeへ適用する。

目的:
- 実装が動くか
- coverageは足りるか
- UNAVAILABLEが正しく出るか
- Long/Short対称性が保たれるか
- 重複ラベルがschema通り保存されるか

確認するだけで、以下はまだ比較しない:
- 勝率
- PnL平均
- PF
- 「FOMOは負ける」
- 「ナンピンは悪い」
- 「逆に張れば勝てる」

---

## 8. test

最低限:

- Long/Short direction symmetry
- threshold boundary
- missing feature -> UNAVAILABLE
- FOMO/Late重複
- adverse add vs profit pyramiding分離
- Revenge candidateのepisode sequence
- future leakageなし
- config version固定
- dry-run再現性

---

## 9. 次ゲート

以下がPASSしたら、次回から exploratory behavior classification に進める。

- label definitions完成
- config固定
- schema固定
- tests PASS
- 24episode dry-run完了
- label availability集計完了

その次に「標本拡大前のexploratory分類」を行う。

---

## 作業終了時

- `CURRENT_STATUS.md` 更新
- `NEXT_TASK.md` 更新
- 必要なら `DECISIONS.md` 追記
- テスト実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discordへ完了通知

養分ホイホイには変更を加えない。
