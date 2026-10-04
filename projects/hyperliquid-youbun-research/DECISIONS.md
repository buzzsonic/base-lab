# DECISIONS

## 2026-10-01 過去分析とリアルタイム分析を分離する

- 決定内容: 過去データによる行動分析と、これからWebSocketで蓄積するリアルタイム観測を別データセットにする。
- 理由: 過去データだけでは任意時点のmargin状態、清算価格、清算直前equityを正確に復元できない。
- 影響範囲: 過去分析はEntry/Exit/PnL/FOMO/Late/ナンピン/Revenge/size/holding/OI/volume/Funding/price。リアルタイムはaccount state/leverage/liquidation/fills/funding/trades/BBO/L2。
- 未解決事項: 観測対象wallet集合、WebSocket運用期間、保存容量、coverage合格基準。

## 2026-10-01 数量一致だけでなくstartPosition連続性を品質ゲートにする

- 決定内容: 完結episodeの数量一致に加え、連続性エラー0、TWAP endpoint非上限、perp fillありを行動分析条件にする。
- 理由: TWAP欠落があってもepisode数量だけは一致する場合がある。
- 影響範囲: 1口座・完結5episodeを現分析母集団から除外。
- 未解決事項: 将来のtime-range TWAP取得方法またはアーカイブ経路。

## 2026-10-01 push成功後だけDiscord完了通知を送る

- 決定内容: 実装・テスト・状態更新・commit・pushの成功後にのみSUCCESS通知する。
- 理由: 通知時点でGitHubが共有正本になっていることを保証するため。
- 影響範囲: `scripts/notify_discord.py`と養分くんプロジェクトの終了手順。
- 未解決事項: `YOUBUN_DISCORD_WEBHOOK_URL`の安全な設定。

## 2026-10-01 Discord Webhookを養分くん専用Secretへ分離する

- 決定内容: GitHub ActionsはRepository Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN`を参照し、実行時だけ`YOUBUN_DISCORD_WEBHOOK_URL`へ渡す。
- 理由: 既存プロジェクトの共通Secretを上書きせず、通知先と障害範囲を分離するため。
- 影響範囲: `Youbun Research Completion Notification`のみ。既存のDiscord通知workflowは変更しない。
- 検証結果: PR #6でUser-Agentを明示し、workflow run `36873558111`が成功。専用Secret経由の通知経路を有効化済み。

## 2026-10-02 episode再構成の層別目視ゲートを通過する

- 決定内容: eligible 10口座・完結61episodeの全件自動照合と、全口座・全主要層を含む20episodeレビューで重大差異0のため、再構成ゲートをPASSとする。
- 根拠: entry/exit境界、方向、数量、平均価格、追加、部分決済、反転、closedPnl、fee、Funding、builderFee包含、同一時刻順序をraw fillから独立再計算した。
- 許容誤差: 数量1e-8、価格・PnL・fee・Funding 1e-6。
- 影響範囲: 次はTWAP/Funding/builder fee会計照合の最終確認へ進む。行動分類はまだ開始しない。
- 制約: 目視サンプルは20/61。過去cross-margin状態と清算距離は対象外。eligible口座のTWAP追加は0件で、TWAP上限口座は除外を継続する。

## 2026-10-02 会計品質ゲートを通過する

- 決定内容: eligible 10口座・完結61episodeのclosedPnl、fee、Funding、net PnLが全件一致し、builderFee二重計上0のため会計ゲートをPASSとする。
- 会計式: `episode net PnL = closedPnl - fee + Funding`。公式fillの`fee`は`builderFee`を含むため、builderFeeを再加算・再控除しない。
- 実データ: Funding非zero 44episode・合計-1,004.713607 USDC。builderFee非zero 9episode・合計565.678405 USDC。
- TWAP: eligible口座の追加0件。2,000件上限かつcontinuity error 15件の口座は除外を継続し、欠落sliceを推定しない。
- 既知WARN: 旧cacheのperp fill 0口座にstored eligible flag不整合1件。現行コードと今回の抽出は再計算条件で除外済み。次回PoC再生成時にcacheを更新する。
- 影響範囲: 次は5分市場系列coverageを定量化する。行動分類はまだ開始しない。

## 2026-10-02 市場coverageをseries別に判定する

- 決定内容: entry特徴量はentryを含む5分足を除外し、entry時刻を5分境界へ切り下げた直前12本だけを使う。entry後12本は評価用namespaceへ分離する。
- 実データ: 61episode中、FEATURE_READY 0、PARTIAL 24、NOT_READY 37。OHLCV/volumeは24/61で完備、Fundingは60/61でentry以前2時間内に観測、historical mark/OIは0/61。
- 欠測処理: mark/OIは空欄NULL、Funding不足も0ではなくmissingとして保存する。37episodeのcandle不足は直近5,000本制限または市場履歴取得不能として除外する。
- 許容範囲: PARTIAL 24episodeではpast-onlyのprice return／volume特徴量だけを明示的に許容する。mark/OI/crowding依存分析へは使わない。
- 理由: 公式Info APIは現在のmark/OIを返すが過去時系列endpointではなく、公式archiveも月次程度・遅延／欠測あり。未確認の過去値を推定すると品質ゲートを壊す。
- 影響範囲: 次はPARTIAL集合への限定的なpast-only特徴量付与。行動分類はまだ開始しない。

## 2026-10-02 限定past-only特徴量ゲートを通過する

- 決定内容: PARTIAL 24episodeに対し、entry直前12本だけからprice return、volume、local structure、BTC relative、Funding rateを生成し、限定特徴量ゲートをPASSとする。
- 実データ: price/volume/local structure/BTC relativeは24/24、Funding rateは23/24。historical mark/OIは0/24でNULLを維持。
- 時点契約: entry足、未来足、exit、PnL、MFE/MAEを計算interfaceへ渡さない。同一timestamp candleの重複または12本未満はwindow全体を不適格にする。
- 定義: returnはlookback内の最初のopenから最後のclose、volume比は直近区間をそれ以前の同幅換算量と比較、breakout distanceはLONG/SHORT方向へ整合させる。詳細は`features/past-only-2026-10-02/feature_definitions.md`。
- 再現性: 24 episode ID一意、数値特徴量は全件有限、range positionは0〜1、cached再実行で成果物がbyte-identical、26 tests PASS。
- 影響範囲: 次は行動ラベル定義の事前登録。24件での分類結果はpipeline検証に限定し、統計的な成績結論には使わない。Crowding/Trapped/Liquidationは必要series不足のため保留する。

## 2026-10-02 行動ラベルv1を事前登録する

- 決定内容: FOMO、Late、Averaging Down、Profit Pyramiding、Revenge Candidateの定義・閾値・必要入力・tri-state schemaをv1.0.0として固定する。
- 閾値: FOMOは方向15分return 1%以上・15分volume ratio 1.5以上・方向range位置80%以上等、Lateは方向1時間return 2%以上・方向range位置85%以上・range端から0.5%以内、追加は既存建玉5%以上かつ平均建値から5bp以上、Revenge候補は損失後60分以内かつinitial notional 1.25倍以上。
- 重複: ラベルは非排他。missing required inputはFALSEでなくUNAVAILABLE。心理状態は断定せずRevengeはcandidateとする。
- dry-run: 24件でFOMO 1、Late 2、Averaging Down 4、Profit Pyramiding 8、Revenge Candidate 4、Revenge UNAVAILABLE 6。PnL・勝率・MFE/MAE・post-entry outcomeは出力へ含めない。
- 最低標本: exploratory outcome比較は最低labeled 100件＋control 100件、confirmatoryは全500episode以上・各label-side cell 50件以上・held-out期間を要求する。
- 変更管理: dry-run後にv1閾値を上書きしない。変更案はv2として別管理し、v1結果を保持する。
- 影響範囲: 次はoutcome-blindのラベル品質レビュー。Crowding/Trapped/Liquidation/逆指標評価は引き続き保留する。

## 2026-10-02 探索サマリをoutcome-freeに限定する

- 決定内容: PHASE 3はlabel件数、wallet/coin/side偏り、重複、UNAVAILABLE率だけを集計し、PnL・勝率・PF・MFE/MAE・post-entry returnを含めない。
- 理由: 24episodeでは結果を見た閾値調整と過剰解釈の危険が高く、まずラベルの発火分布と実装品質だけを確認するため。
- 影響範囲: 次は全TRUE例と層別FALSE例のoutcome-blindレビュー、その後100〜500口座・数千episodeへの拡大設計。

## 2026-10-02 ラベル品質レビューPASS後は100口座pilotから拡大する

- 結果: 全TRUE 14episodeと層別all-FALSE 7episodeをoutcome-blindで再照合し21/21 PASS。v1閾値変更なし。
- 制約: add判定の個別pre-add平均・価格・stable order traceが成果物に未保存。pilot前にoutcome-free evidence tableを追加する。
- 拡大: 100口座pilotで再構成・会計誤差0と層別除外率を確認し、PASS時のみ500口座へ進む。eligible完結episode目標は2,000件。
- 期間: exploratory 60%、validation 20%、held-out confirmatory 20%を収集前に固定する。
- 影響範囲: outcome評価は最低標本を満たすまで開始しない。v1閾値は凍結を継続する。

## 2026-10-02 add evidence gateを通過する

- 結果: outcome-free add event 2,464件、source trace不明0。24episode dry-runのAveraging Down 4件・Profit Pyramiding 8件と一致。
- 停止判断: main上に行動結果を含まない固定discovery universeがないため、100口座manifestを推測で作らない。
- 次: discovery sourceと取得時刻を固定してから、層化100口座を再現可能に選ぶ。

## 2026-10-02 pilot-100再構成の重大差異で停止する

- Sampling: Hoihoi data commit `4fea9437aac3036f7fb64abc74ae37e23a7e906a`の公開Trades実時間598 walletから、size・frequency・symbol・activityだけを使い100 walletを固定。PnL・ROI・勝敗・behavior labelは不使用。
- 収集: fills・TWAP・Fundingを100/100 walletで取得、endpoint失敗0、pagination safety cap hit 0。
- 差異: 初回再構成46,182 episodesのうちquantity mismatch 107件 / 33 wallets、continuity error 3,790件 / 47 wallets。
- 決定: `NEXT_TASK.md`の重大再構成差異に該当するため停止。OHLCV、label適用、500口座拡大は行わない。
- 次: raw traceでfill/TWAP merge、同一timestamp順序、API page boundary、left censoringを原因分類し、欠落fillを推定しない。

## 2026-10-03 historical pilotを止めforward収集へ設計変更する

- 確定原因1: `userFillsByTime` / `userFunding`のページ境界で`max(timestamp)+1ms`としていたため、同一millisecondの残りrecordsを欠落させた。境界timestamp overlap＋dedupへ修正する。
- 確定原因2: 通常fillsとTWAP sliceの同一timestamp順序が単純連結で壊れた。観測済み`startPosition → afterPosition`鎖でinterleaveする。
- 実証: P077はfills 12,079→12,329、continuity 6→0。Funding全体は505,011→535,462。
- 制約: 修正版再取得時に36口座がrolling retentionで旧固定期間先頭を失い、追加のTWAP retention gap 5、復元不能fill gap 2等を含めeligibleは44/100に留まった。
- 決定: eligible 44口座・完結22,973episodeはquantity mismatch 0 / continuity error 0だが、56%除外のhistorical pilotはsampling biasが大きいため不採用。固定100口座のappend-only forward collectorへ変更する。
- 禁止: 欠落fill推定、口座差替え、OHLCV/label/500口座拡大。forward収集設計とshadow quality Gate後に再開する。

## 2026-10-03 fixed-100 forward collectorはREST overlapを正本にする

- 決定: 固定100口座の`userFillsByTime`、`userTwapSliceFillsByTime`、`userFunding`を定期RESTでappend-only保存する。fills/TWAPは20分、Fundingは60分周期。
- WebSocket: user-specific subscriptionはIPあたり10 unique users上限のため、100口座を同条件で観測する正本にはしない。
- 完全性: 前回成功pollから20分overlapし、末尾timestampをinclusiveで再取得する。raw重複は保持し、canonical viewでendpoint・wallet・dedup keyにより除外する。
- Rate limit: 応答件数からweightを見積もり600 weight/minute以下に抑え、公式1200 weight/minute上限へ50%余裕を残す。
- 保存: data branchの`forward-data/`へimmutable runとcheckpointを保存する。失敗時はcheckpointを進めず、gapを推定・前方補完しない。
- Gate: 最低7日間のShadow Gateを通過するまでOHLCV、behavior label、500口座拡大を再開しない。

## 2026-10-04 forward collector v1を凍結しv2へ分離する

- 事実: 20分cronに対するscheduled runは約3〜4時間間隔で2回だけだった。runは2/2成功したが、各runのfillsは109,786件／103,470件。
- 品質問題: P031とP035が各run 10,000 fillsを超え、`retention_risk=true`。成功statusだけでは保持範囲内の完全性を保証できない。
- 決定: v1 workflowを停止し、`forward-data/`は監査証跡として凍結する。欠落を推定・補完せず分析対象にしない。
- v2: `forward-data-v2/`へ新しいanalysis startを固定し、5分ごとの起動要求＋shared concurrencyで直列化する。
- Fail-fast: endpoint failure、page cap、retention riskをmanifest/stateへ保存した後、workflowを失敗させる。
- 影響範囲: v2の初回100口座runと次runが合格するまで7日Gate開始日は未確定。OHLCV、label、500口座拡大はHOLD。

## 2026-10-04 forward collector v2も凍結する

- 事実: canary run `37156803479`とfixed-100初回run `37157149516`は合格したが、初回scheduled run `37169042021`は直前full runから約3時間35分後に開始した。
- 品質問題: P031で12,524 fills、P035で11,365 fillsとなり、2口座で`retention_risk=true`。endpoint failure 0、cap hit 0でもcoverage完全性は成立しない。
- Fail-fast検証: raw・manifest・stateをdata branch commit `7d4c28e`へ保存した後、quality flagによりworkflowが意図どおりfailureとなった。
- 決定: v2 workflowを`disabled_manually`へ戻し、実行中・queued 0を確認。v2 raw/stateは監査用に凍結し、次版へ混ぜない。
- 次: GitHub Actions scheduleを正本schedulerにせず、20分以内の実行を外部から実測・監視できる方式を設計する。新namespace・新analysis startで再開する。
- 影響範囲: 7日Shadow Gateは未開始。OHLCV本分析、behavior label本適用、500-wallet expansionはHOLDを継続する。

## 2026-10-04 forward collector v3はVPS systemd timerを正本にする

- runtime: Ubuntu VPS + Docker、schedulerはsystemd timer。GitHub Actions scheduleは使用しない。
- cadence: 5分ごとに起動要求し、`flock`とoneshot serviceでsingle-flightにする。1 runは19分でtimeoutし、20分以内に完走または明示的FAILさせる。
- transaction: endpoint failure、retention risk、cap hit、timeout時はcheckpointを進めない。raw manifestが完成した品質FAILは監査証跡として保存する。
- namespace: `forward-data-v3/`と`forward-v3`を固定し、v1/v2 raw/stateを混ぜない。
- data push: dirty checkout、pending push失敗、fast-forward失敗、push conflictでは収集・次runを停止する。
- CI: scheduleなしの専用workflowで55 testsとDocker buildだけを検証する。run `37173864803`でPASS。
- 影響範囲: VPS canaryとfixed-100 3連続runが全Gateを満たすまで7日Shadow Gateは未開始。
