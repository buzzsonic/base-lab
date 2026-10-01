# Hyperliquid「養分くん」行動研究計画

> 状態: Phase 1 設計案。売買・署名・資金移動・Discord送信は行わない。

## 1. 研究目的と非目的

公開データだけを使い、長期損失と関連する行動を口座集団で検証する。対象は FOMO、late entry、含み損追加、revenge trade、勝ち後のサイズ増加、利小損大、高レバ、清算、crowding である。個別ウォレットの晒しや、自動売買シグナルの実装は目的にしない。

観測事実、再構成値、仮説を分離する。相関を因果と呼ばず、費用・Funding・欠測・母集団・時刻整合・検証期間を必ず表示する。

## 2. データソースと用途

| データソース | 用途 | 主な制約 |
|---|---|---|
| Hyperliquid Info API | fills、TWAP slices、funding、現建玉、現在の清算価格、注文履歴、OHLCV、market context、L2 snapshot | 履歴件数上限、時系列レスポンスのページング、過去の口座状態は原則返さない |
| Hyperliquid WebSocket | trades、BBO/L2、candle、user fills/events、現在以降の口座・建玉状態 | 接続開始前の状態は復元不能。切断・再接続・欠測管理が必要 |
| 公式 leaderboard JSON | PoC候補と層別サンプルの入口 | ランキング由来だけでは survivorship bias を除けない |
| HyperCore explorer / archive | ブロック・公開イベントの補完候補 | 全履歴の取得コストとスキーマを別途検証する |

## 3. 取得可能性分類

### 直接取得できる

- wallet/account ID、fills、side、fill price/size/time、startPosition、closedPnl、fee、maker/taker相当 (`crossed`)
- 現在の open positions、entry price、position size、unrealized PnL、leverage設定、liquidation price、margin mode、margin used
- 現在および直近の open/historical orders、order type、status
- user funding、TWAP slice fills、OHLCV、mark/oracle price、OI、current/historical funding、L2 snapshot、public trades
- WebSocket user eventに現れる liquidation event（監視開始後）

### 他データから再構成・推定できる

- closed position、average entry/exit、trade duration、追加、部分決済、ドテン、zero-to-zero position episode
- fill間の建玉増減、ナンピン候補、revenge trade、size-up-after-win
- candle/mark系列が被る期間の MAE/MFE、entry前return、volume/OI/funding regime
- 収集開始後の equity・position・effective leverage・unrealized PnL・liquidation distance の時系列
- liquidation fill/eventを観測できた場合の実清算、または `dir` 等に基づく清算候補

### 現状そのままでは取得できない

- 任意の過去時点における口座全体の cross-margin状態、正確な実効レバレッジ、清算価格、利用可能証拠金
- 収集開始前の連続的な含み益/含み損、equity、清算直前状態
- 全市場参加者の完全なLong/Short比率
- 未公開・未約定注文、トレーダーの意図
- 過去L2の完全復元（事前収集または別アーカイブなし）

## 4. 重点項目の扱い

- **実際の使用レバレッジ**: 現在スナップショットでは直接値と position value/account equity を併記。過去は同時刻equityスナップショットがない限り欠測。
- **清算価格**: 現在値は `clearinghouseState`。過去推定は当時のmargin mode・equity・他建玉が必要なため、公式値の保存開始前は原則欠測。
- **清算済み**: liquidation event/fill/order statusを優先し、単なる大幅損失と区別する。
- **ナンピン**: 同一episode内で、追加直前markがその時点の平均建値より不利な同方向追加。
- **含み損益推移**: mark系列と再構成positionが揃う区間のみ計算。cross口座の清算余力とは区別する。

## 5. サンプル設計

PoCは10〜20口座。leaderboardの利益・損失・出来高・equity層に加え、公開tradesから時点抽出した非ランキング口座を混ぜる。層別条件と抽出時刻を保存し、有名口座だけに偏らないようにする。

拡張は 20 → 100 → 500 → 1,000。5,000/10,000は、直近履歴上限とAPI weightを踏まえ、fillsの必要期間・欠測率・重複率を先に評価してから判断する。

## 6. 定義（訓練期間で確定し、検証期間では固定）

- **Late Long/Short**: 価格急変または直近高安ブレイク後に同方向へ新規episodeを開始し、entry時点が急変窓の終盤にある行動。閾値候補を複数比較し、最終定義はtrainで固定する。
- **Trapped Long/Short**: entry後に方向調整済みreturnが -2/-5/-10%に到達し、未決済建玉が残る状態。結果を損切り、追加、継続、清算へ分類する。
- **Liquidation Cascade**: 同銘柄・同方向の清算が短時間に複数観測され、同時に価格が清算方向へ継続、OI低下、出来高増加を伴うイベント。10秒〜15分のforward pathをイベント重複排除後に測る。
- **Revenge Trade**: 損失episode終了または清算後1/5/15/30/60分以内の新規episode。銘柄、方向、size ratioを分ける。

定義にトレード後の最終損益を使用しない。`late` や `trapped` は、その時点までに観測可能な情報だけでラベル付けする。

## 7. 推奨データ構造

DuckDBを分析正本、Parquetを不変raw/processed層にする。

- `raw/api_responses`: endpoint、request hash、fetched_at、payload、HTTP metadata
- `raw/fills`, `raw/twap_fills`, `raw/funding`, `raw/orders`
- `raw/candles`, `raw/asset_ctx`, `raw/trades`, `raw/bbo_l2`, `raw/account_snapshots`
- `processed/position_episodes`, `processed/episode_events`
- `processed/market_features`, `processed/account_features`, `processed/crowding_events`
- `quality/fetch_runs`, `quality/coverage`, `quality/reconciliation`

主キー、source timestamp、ingest timestamp、source endpoint、取得window、schema versionを保存する。同一ミリ秒fillはサーバー返却順を保持し、`tid`で並べ替えない。

### 過去分析とリアルタイム観測を分離する

- `historical_*`: fills、TWAP slices、Funding、candle、asset contextから再構成できる範囲。過去margin、過去liquidation price、清算直前equityを推測で補完しない。
- `realtime_*`: 収集開始後のaccount state、position、leverage、liquidation price、fills、liquidation user event、funding、trades、BBO/L2をsource timestamp付きで保存する。
- 過去分析の行動ラベルと、リアルタイム観測でのみ作れる`trapped/liquidation/cascade`ラベルを同じ列で混在させない。availability classとcoverageを必須列にする。

## 8. API制限と収集設計

- RESTはIP単位のweight上限を尊重し、endpoint別weightと返却行数追加weightを予算化する。
- `userFills`/historical orders/TWAP slice fillsは直近件数上限があるため、time-range endpointとcheckpointを使う。ただし取得可能期間そのものの限界を完全履歴と誤認しない。
- candleは直近5,000本のため、5分足では約17日分しか一度に公式保存されない。30/90/180日研究には継続収集または信頼できるアーカイブが必要。
- exponential backoff、timeout、rate budget、request cache、再開可能checkpoint、raw response保存を必須にする。

## 9. 再構成と品質ゲート

`startPosition`、`side`、`sz`から銘柄別zero-to-zero episodeを作り、反転fillは旧episodeのcloseと新episodeのopenへ数量按分する。TWAP slice fillsを照合し、fill欠落と二重計上を検査する。

PoC通過条件:

1. entry quantity = exit quantity（完結episode）
2. episode合計のclosedPnl/feeがraw合計と許容誤差内
3. 同一ms順序、部分決済、追加、反転、清算候補のfixtureが目視結果と一致
4. 市場系列coverageと欠測率を銘柄・期間別に表示
5. 10〜20口座のサンプルepisodeを人手確認できるHTML/CSVで出力

## 10. 統計設計

- 時系列で train / validation / out-of-sample を分割し、ウォレットとイベントの重複を管理する。
- 同一急変イベント内の多数口座を独立標本として数えない。event-cluster robust SEまたはイベント単位bootstrapを使う。
- 行動単独、market regime、銘柄流動性、wallet fixed/random effect相当を比較する。
- 収益はfee・Funding込み。実行可能性を論じる場合だけ、別途slippageを加える。
- 多重検定を補正し、効果量・信頼区間・標本数を表示する。
- YOUBUN SCOREの重みはtrainで推定し、OOSでROI/PF/DD/清算との単調性と較正を確認する。初期配点は結論に使わない。

## 11. 実装フェーズ

1. 公式API schema probeと可否表の確定
2. PoC口座サンプリング、raw cache、coverage監査
3. TWAP/Funding/builder feeのepisode帰属とzero-to-zero再構成
4. 完結episodeのサンプル目視検証
5. 5分足coverageを定量化し、不足区間では市場特徴量を欠測にする
6. episodeへpast-only市場特徴量を付与
7. FOMO/Late/Nanpin/Revengeのラベラー
8. 100〜500口座・数千episodeへ拡張し、数量/PnL/fee照合誤差0を再確認
9. realtime観測DBを別系統で継続収集
10. 統計分析、regime/銘柄別比較、クラスタリング
11. OOS固定検証
12. `reports/youbun_report.html` 作成

## 12. 想定バイアス

leaderboard selection、survivorship、履歴上限によるleft truncation、現在状態だけ残るright censoring、薄い銘柄の価格欠測、同一市場イベントによる擬似反復、複数閾値探索、ウォレット分割、bot/MM混入、cross-margin清算推定誤差、delisted/remapped assetを明示的に追跡する。

## 13. 最初の成果物

最初に出すのは最終結論ではなく、PoCのデータ品質レポートと再構成サンプルである。主要行動ラベルの目視確認を終えるまで100口座以上へ拡張せず、リアルタイム「養分センサー」も実装しない。
