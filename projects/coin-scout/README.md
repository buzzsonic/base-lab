# coin-scout

Hyperliquid上場銘柄から観測上の異常を探し、「何が起きたか・何が不足しているか・次に何を見るか」をDiscordへ通知する読み取り専用Botです。売買方向、参加者の捕まり、清算、収益性は推定・断定しません。自動売買機能はありません。

## 既存機能と実行間隔

- 朝8:00 / 夜20:00 JST: 従来の定時ダイジェスト。該当ゼロ時の生存確認、新規上場、エラー通知を維持
- 約5分ごと: 別workflowで全監視銘柄の観測を永続保存。Actions cronの予定時刻ではなく実際の取得時刻を使用
- 詳細通知: 異常度が高く、データ充足度60%以上で、前回通知から重要な状態変化がある上位3銘柄

GitHub Actionsのscheduleは遅延・欠落し得ます。比較点は対象時刻±3分以内の実測値だけを採用し、補間しません。履歴不足は「蓄積中」、遅延は欠測として記録します。

`metaAndAssetCtxs`は市場値ごとのデータ元時刻を返さないため、`source_at_ms=null`と`source_timestamp_status=not_provided_by_metaAndAssetCtxs`を保存します。観測時刻をデータ元時刻に偽装せず、鮮度は不明として扱います。

## 監視対象と取得元

母集団はHyperliquidの稼働中perpetualです。そのうちBinance/Bybit直接24h出来高$10M以上、またはCoinGecko集計$20M以上を監視します。GitHub-hosted runnerではBinance Futures/Bybitが地域制限されるため、流動性選別にはBinance公式spot mirrorとCoinGeckoを代替利用します。

市場観測値はHyperliquid `metaAndAssetCtxs`と`recentTrades`から取得します。全銘柄の`candleSnapshot`/`recentTrades` pollingは実測で429になったため、価格経路は5分ごとの一括snapshotを保存し、約定は1runあたり3銘柄をローテーション取得します。`recentTrades.side`は公式API表記の`B=買い手主導`、`A=売り手主導`として集計します。対象外、API失敗、返却上限で区間開始まで届かない場合はpartialとして通知根拠から除外します。ローソク足の色からCVDを推定しません。全銘柄の連続CVDには、常時稼働環境でのWebSocket収集が別途必要です。

## 指標定義

- 価格変化: 5m/15m/1hは実測snapshot間、24hはHyperliquidの`prevDayPx`
- OI変化: `openInterest`の数量建てを5m/15m/1hで比較。ドル建てOIも保存するが、新規建玉の判定には使わない
- Funding: 元値、元interval（HLは1時間）、1時間率を保存。銘柄別の過去14日・1時間1標本によるmedian/MADとrobust-zを計算。24標本未満は蓄積中。年率表示は参考の単純換算のみ
- 約定偏り: 5m/15mの買い手主導約定額－売り手主導約定額、および総額で割った値。完全区間だけ評価
- 高安値位置: 直近1時間の実測5分snapshot高値からの下落率、安値からの上昇率、各更新からの経過時間、観測経路の平均絶対変化に対する距離。OHLCではないためATRとは呼ばない
- OI/出来高: OI数量・OIドル・24hドル出来高を区別して保存。OI/出来高比をスクイーズ確定指標として扱わない

### 異常度

方向期待値ではない0–100の観測異常度です。価格30、数量OI25、Funding15、直接約定偏り20の相対重みを、取得できた項目間で再正規化します。高安値位置は価格変化と相関するためスコアへ重ねず、文脈表示だけに使います。欠測項目は0点にせず分母から外し、中核8項目の`core_data_completeness_pct`と、Funding分布・約定・高安値を含む`data_completeness_pct`を別に保存します。相関指標の数を「独立した根拠数」や勝率として表示しません。式・閾値を変えた場合は`LOGIC_VERSION`を更新し、過去ログを上書きしません。

## 保存形式と永続性

`data`ブランチへ以下を保存します。

- `coin-scout/data/observations/YYYY-MM-DD/observations-HHMM.jsonl.gz`: 1観測×1銘柄。値、特徴量、発火/非発火/不足理由、鮮度、欠測、設定version
- `coin-scout/data/observations/YYYY-MM-DD/outcomes-HHMM.jsonl.gz`: 発火eventと、非発火比較群の毎時決定的サンプルについて、そのrunで到達した観測後5/15/30/60分の実測終点、最大上昇・最大下落、使用した5分snapshot経路。方向を事前定義した将来検証時にのみMFE/MAEへ変換する
- `coin-scout/.state/collector_state.json`: 26時間の比較用snapshot、14日Funding標本、通知抑制状態、watchlist cache

event IDは`logic version + exchange + symbol + 実測5分bucket`のSHA-256短縮値です。同じbucketの再実行はgzipログへの追記時に重複排除します。gzipは5分bucketごとの不変ファイルにし、Gitで日次バイナリ全体を毎回書き直す膨張を避けます。全観測は保存し、将来outcomeは全発火event＋毎時の非発火対照群に限定して比較可能性と容量を両立します。ログは削除せず長期保持し、計算用stateだけ期限を設けます。94銘柄の初回実測は約10.7KB（観測のみ）でした。概算約3.1MB/日＋outcome/状態履歴ですが、実圧縮率を週次確認します。GitHub容量が問題になれば、履歴証跡を消さずRelease/S3等へ移管します。

## 通知の読み方

表示するのは「価格上昇＋数量OI増加」「建玉減少を伴う急変」「買い手/売り手主導約定の偏り」「Funding分布乖離」などの観測事実です。「ショート捕まり」「ロング過密」「スクイーズ進行・終了」「ロング/ショート優勢」は表示しません。

次の行動も売買指示ではなく、「次回、高安値更新・数量OI継続・直接約定偏り継続・欠測解消を確認」とします。清算データは取得していないため、清算確認とは表示しません。

## ローカル確認

```sh
cd projects/coin-scout
python -m pip install -r requirements.txt
PYTHONPATH=../.. DRY_RUN=true python -m src.main
PYTHONPATH=../.. DRY_RUN=true COLLECTOR_MAX_COINS=3 python -m src.collector
PYTHONPATH=../.. python -m unittest discover -s tests -v
```

`.env.example`で収集・通知設定を変更できます。Discord Secretは`DISCORD_WEBHOOK_URL`です。サンプル通知中の数値を架空値として示す場合は、必ず「架空データ」と明記してください。

ロジック変更履歴は`LOGIC_HISTORY.md`に保存します。

## 将来検証

outcomeログは方向ルールを本番通知に入れるものではありません。入口・出口・約定方式・費用・Funding・開発/評価期間を事前登録したうえで、通知/非通知/評価保留を比較し、連続eventを同一クラスタとして扱います。20–30件やPF>1だけで採用しません。
