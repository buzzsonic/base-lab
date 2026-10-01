# 養分ホイホイ research plan

## 1. 候補ウォレット取得元

1. 公式leaderboard全体を月間出来高×現equityの16層へ分け、PnL順ではなく決定論的hashで層別抽出する。
2. 公式WebSocket `trades` の凍結済みpublic captureから、最初に観測したbuyer/sellerを成績非参照で時点抽出する。PoCでは既存actor-event-dbの公開Trades rawを再利用し、出所ファイルを保存する。
3. 本運用では専用の短時間Trades collectorと公式node fills / explorer blockの低頻度取り込みを追加する。S3はRequester Pays、月次程度、欠測保証なしなので必須経路にしない。

PoCは1と2を50:50でround-robinし、単一ソース上限60%。重複時はprovenanceを連結する。

## 2. 各取得元のbias

| source | 主なbias | 緩和策 |
|---|---|---|
| leaderboard | survivorship、whale、activity、期間窓 | PnL非使用、volume/equity層別、最大比率ゲート |
| live public Trades | active/MM bias、観測時間帯、熱門銘柄 | JST時刻を変えた複数窓、銘柄層別、maker集中を分類 |
| node/explorer fills | 転送費・処理量、schema drift | 増分checkpoint、source schema version、raw保持 |

研究sampleの母集団は「APIで現在確認可能なHyperliquid活動口座」であり、全ユーザー母集団ではない。

## 3. 重複排除方法

EVM addressをlowercase 42文字へ正規化してwalletを主キーにする。source間重複は削除せず、`discovery_source` と `discovery_detail` を結合して発見経路を保持する。master/subaccountの名寄せは推測せず別口座とする。

## 4. candidate → active sample昇格条件

- first_seenから7日以上（設定可）
- 直近30日perp fillsが3件以上（設定可）
- 最新state取得成功、必須列欠測なし
- BOT/MM/arbitrage/funding-arbitrage/farm疑いがない
- fill上限2,000到達時は完全履歴とみなさず、頻度等の下限値として扱う
- sample生成時点で条件を固定し、`sample_version` と `sample_created_at` を付けた不変snapshotを残す

勝敗、PnL、ROIは昇格条件にしない。

## 5. BOT/MM/裁定/farm判定

全てheuristicな疑いラベルであり削除ではない。閾値は`config.json`。

- BOT: fills/active day、median inter-arrival、30日fills
- MM: BOT傾向＋maker比率＋両side取引
- Funding裁定: 現在のSpot保有と反対向きPerpが同一資産・概ね同サイズ
- Arbitrage: funding-neutralを含む。将来は同時刻の多市場/spot-perp反対売買を追加
- farm: 小額・高頻度・多数銘柄

`suspicion_reason`に発火理由を残す。通常sampleからは除外するがregistryと別CSVに保持する。

## 6. Spot/Perp分類

fillsの`coin`が`@`始まりならSpot、それ以外はPerp。表示名のremapは`spotMeta`取得後の補助テーブルで解決する。Perp最低活動条件にSpot fillを足さない。

## 7. Equity取得方法

公式`clearinghouseState.marginSummary.accountValue`を取得時点のperp account equityとして保存する。cash balanceは`totalRawUsd`、建玉は`assetPositions`から計算する。取得不能値はnullで、過去値を捏造しない。

## 8. 出金と損失の区別

週次equity低下が閾値を超えた口座だけ、同窓の`userNonFundingLedgerUpdates`を取得する。withdrawal/transfer outがequity差に概ね一致する場合は`WITHDRAWAL_SUSPECTED`とし、depletion件数から除外する。cross-subaccount移動や未取得ledgerの可能性があるため断定しない。

## 9. rapid depletion判定

比較可能な7日間snapshotで70%以上減を`RAPID_DEPLETION`、50%以上70%未満を`NEAR_DEPLETION`。日曜snapshot失敗またはstaleなら判定を`SKIPPED_STALE_SNAPSHOT`とする。

## 10. inactive判定

直近30日Perp fillが設定件数未満ならinactive。初回取得で2,000件上限に達した口座はactive判定は可能だが、正確なtrade_countやbot判定には`data_limit_note`を付ける。

## 11. 補充方法

前回ピークactive sample比で15%以上減少したらdiscovery budgetを増やす。固定目標数を強制せず、source/size/bot比率ゲートに違反する補充は採用しない。

## 12. データ構造

- `wallet_registry.parquet`: 全状態と分類、発見provenance、品質列
- `research_sample.parquet`: 現行固定sample
- `outputs/samples/sample_YYYYMMDD.parquet`: 過去sample（不変）
- `outputs/snapshots/date=YYYY-MM-DD/*.parquet`: weekly account state partition
- `arbitrage_wallets.csv` / `ARBITRAGE_WALLETS.md`: 人手確認用
- `poc_manifest.json`: 件数・bias・欠測・cap

大規模raw/stateは`data`ブランチ、mainにはcode/docsと小さなcurrent indexのみを置く。

## 13. GitHub Actions構成

- `youbun-hoihoi-snapshot.yml`: 土曜15:00 UTC = 日曜00:00 JST。stateをbatch収集しdata branchへcommit。
- `youbun-hoihoi-weekly.yml`: 日曜15:00 UTC = 月曜00:00 JST。snapshot freshness確認→分類→discovery→sample version→summary→push→Discord。
- workflowは`concurrency`で直列化。将来matrix化する場合も、API全体のbudgetを共有するbatch artifact方式にする。

## 14. Rate Limit対策

公式上限はREST合計1,200 weight/分。`clearinghouseState`/`spotClearinghouseState`はweight 2、通常infoは20、fills系は返却件数追加weightがある。1.25秒の共有間隔、Retry-After、指数backoff、raw cache、checkpointを使用する。5,000件へ拡張する前に実runのweight/所要時間を測る。

## 15. データ量対策

ZSTD Parquet、日付partition、差分取得、raw cache、checkpoint、退場口座の月次集約を用いる。毎回全履歴を再取得しない。raw JSONをmainへcommitしない。

## 16. 失敗時処理

snapshot manifestが当週・successでなければdepletion判定のみ停止。discovery、候補追加、分類可能な既存データ処理は続ける。部分成果はstagingへ書き、品質ゲート通過後にcurrentをatomic replaceする。

## 17. Discord通知

secretは`YOUBUN_HOIHOI_DISCORD_WEBHOOK_URL`のみ。未設定時は明示的SKIPPED。成功/部分失敗/完全失敗の3形式とし、wallet addressやsecretは通知しない。

## 18. 養分くんへの受け渡し

養分くんは`research_sample.parquet`の`wallet`,`sample_version`,`sample_created_at`を入力契約とする。養分ホイホイの疑いラベルは対象選定用で、養分スコア特徴量へ流用しない。各分析はsample versionを必ず記録する。

## 段階ゲート

200 PoC → 1,000 → 5,000 → 10,000。各段階でduplicate、inactive、bot、whale、leaderboard、spot-only、arbitrage、farmの比率とfill cap率を確認し、処理時間・API429・欠測を合格条件にする。
