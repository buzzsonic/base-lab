# CURRENT_STATUS

更新日: 2026-10-06 JST

## Current Phase

BTC exploratory pipeline検証後、forward core market seriesの分離設計とfixture限定collector実装を完了。core feature READYは0のままで仮説成績評価は開始していない。次の24時間live canaryはVPS配置先のユーザー確認待ち。

## Completed

- 12口座・30日の読み取り専用PoC
- raw fills 7,783、perp fills 5,383、position episodes 84
- 完結・期間開始前持ち越しなし66、数量不一致0、清算観測0
- zero-to-zero、部分決済、追加、反転の再構成
- TWAP/Funding取得とepisode時間窓へのFunding帰属
- startPosition連続性ゲートを追加
- 過去分析とリアルタイム観測のdata contractを分離
- ChatGPT/Codex/GitHub/Discord共有運用を構築
- 養分くん専用Discord通知を実送信確認済み
- eligible 10口座・完結61episodeの境界・数量・価格・PnL・fee・Fundingを独立再計算し、61/61一致
- 勝敗、Long/Short、追加、部分決済、反転、保有時間、fill数を跨ぐ20episodeを匿名化レビューし、20/20 PASS
- eligible 10口座・完結61episodeのclosedPnl、fee、Funding、net PnL会計照合61/61 PASS
- Fundingは44episodeで非zero、合計-1,004.713607 USDC
- builderFeeは9episodeで非zero、合計565.678405 USDC。全件fee内包で二重計上0
- eligible口座のTWAP追加0件、TWAP 2,000件上限口座の除外をtestとレポートで固定
- eligible 10口座・完結61episodeのentry前60分／entry後60分の市場series coverageを全件確定
- entryを含む未確定5分足を除外し、直前12本だけをentry特徴量窓にするpast-only契約をtest化
- FEATURE_READY 0、PARTIAL 24、NOT_READY 37。OHLCV/volume完備24、Fundingは60/61でentry以前2時間内に観測
- historical mark/OIは61件すべてNULL/unavailableとし、推定・0埋めを行わなかった
- PARTIAL 24episodeへentry以前の確定12本だけからprice/volume/local structure特徴量を付与
- BTC相対特徴量は24/24、Funding rateは23/24。mark/OIは24/24でNULLを維持
- 24episode ID一意、数値特徴量有限、range position範囲内、再実行CSV同一を確認
- FOMO / Late / Averaging Down / Profit Pyramiding / Revenge Candidateのv1定義・閾値・tri-state schemaを事前登録
- 24episode dry-runはFOMO 1、Late 2、Averaging Down 4、Profit Pyramiding 8、Revenge Candidate 4。Revenge 6件は前episode不足でUNAVAILABLE
- dry-run成果物にPnL・勝敗・MFE/MAE・post-entry結果を含めず、再実行同一を確認
- PHASE 3としてwallet・coin・side・重複パターン別のoutcome-free分布サマリを作成
- TRUEを含む14episode全件＋層別all-FALSE 7episodeをoutcome-blind再照合し21/21 PASS
- 100口座pilot→500口座拡大、探索60%・validation 20%・held-out 20%、目標2,000episodeの設計を固定
- Hoihoi data commit `4fea9437aac3036f7fb64abc74ae37e23a7e906a`のpublic Trades実時間598 walletからoutcome-freeに100 walletを固定
- sampling duplicate 0、25 strata、再生成byte-identical、split 60/20/20
- 100/100 walletでfills・TWAP・Funding endpoint収集成功、失敗0、safety cap hit 0
- raw fills 674,339、TWAP追加8,452、Funding 505,011、merge後perp fills 680,842
- 初回再構成46,182 episodes、完結uncensored 44,125
- quantity mismatch 107 episodes / 33 wallets、continuity error 3,790 / 47 walletsを検出し停止
- ページ境界末尾timestampへ`+1ms`して同一millisecond recordsを落とす不具合を特定し、timestamp overlap＋dedupへ修正
- 通常fillとTWAP sliceの同一timestamp順序を観測済みstartPosition鎖でinterleaveするよう修正
- 修正版Fundingを100/100再取得し、505,011→535,462 rows（+30,451）
- 修正版fillsと旧固定期間を完全比較できたのは64/100口座。36口座はrolling retentionで期間先頭を再取得不能
- 全品質条件を満たす44口座・完結22,973episodeではquantity mismatch 0、continuity error 0
- 56口座除外はsampling biasが大きいためOHLCV・label・500口座拡大を停止
- 固定100口座のfills / TWAP slice fills / FundingをRESTで継続取得するforward collectorを実装
- 20分overlap、inclusive page boundary、dedup key、immutable raw run、wallet×endpoint checkpointを固定
- 応答weightに応じて600 weight/minute以下へ抑える動的rate pacingを実装
- 1口座公開API canaryで3/3 endpoint成功、failure 0、cap hit 0（観測開始直後のためrecord 0）
- GitHub Actions canary run `37122082323`でtest・3 endpoint・artifact・data branch pushを全て確認
- 固定100口座初回run `37122182275`成功。300/300 checkpoint、failure 0、cap hit 0、retention risk 0
- 初回runはcanary済み1口座をcadence skipし、残り99口座×3系統=297 request成功、fills 507件をappend-only保存
- data branch commit `cf82b02`、固定`analysis_start_ms=1791029567198`、sample SHA `e7ef8b4c...7f994`
- v1 scheduled runは2回だけで、開始間隔は約3時間56分／3時間18分
- v1 scheduled run自体は2/2成功・endpoint failure 0・cap hit 0だが、fillsは109,786件／103,470件
- 高頻度2口座（P031、P035）が各run 10,000 fills超となり`retention_risk=true`。v1期間の完全性は不成立
- collector workflowを2026-10-04に`disabled_manually`確認。実行中・pending 0
- v2 canary run `37156803479`とfixed-100初回run `37157149516`はfailure / retention / cap 0で成功
- v2初回scheduled run `37169042021`は直前full runから約3時間35分後に開始
- v2 scheduled runは99,854 recordsを保存後、P031 12,524 fills / P035 11,365 fillsの`retention_risk=true`を検出して意図どおりFAIL
- v2 data branch commit `7d4c28e`に失敗runのraw / manifest / stateを監査証跡として保存
- v2 workflowも`disabled_manually`へ戻し、実行中・queued 0を確認

## Latest Work

- fixture限定の独立entrypointでasset ctx、1分candle、optional tradesのraw保存を実装。
- 確定1分足だけのcanonical化、restart dedup、candle gap、asset ctx stale、optional障害分離、fail-safe checkpointを7 testで確認。
- WebSocket接続、REST live adapter、VPS deploy、実データ収集は未実施。
- BTC market collectorを`market-core-v1` / `forward-market-core-v1/`として既存wallet `forward-v3`から分離設計。
- coreは`activeAssetCtx`、BTC 1分candle、collector health。BTC tradesはH08用optional、wallet state・BBO/L2・liquidation eventは延期。
- asset ctxにsource timestampが無い場合はNULLを保持し、cutoff前120秒以内だけfreshとする。ctx gapは自動修復しない。
- 1分candleは確定足だけcanonical化し、直近5,000本内の`candleSnapshot`修復だけ許可。修復元と未解決gapを明示する。
- 24時間canaryと連続7 JST日のGateを定義したが、collector実装・VPS deploy・live収集は未開始。
- exploratory限定で連続5分event 5,318件を生成。BTC activity 4,112件、zero activity 1,206件をsource gapと分離。
- H02 new-entry feature 662 window、H04 averaging-down 251 window、H05 past-20 size baseline 2,593 windowをoutcome-freeで生成。
- H07 price outcomeを別fileへ保存し、5/15/30/60分各1,714 windowをREADYと判定。5分足解像度であることをschema名とfield名へ明示。
- event / outcome key一意、future field物理分離、欠測NULL、再実行byte-identical、wallet address非出力を確認。
- historical BTC asset context 0%のためcore feature READYは0。effect size、勝率、p値、逆指標性、仮説採否は未計算。
- 次はmark / OI / Funding、BTC 1分candle、gap healthの最小forward core collector設計。market tradesはoptional group。
- BTC実データ監査で44/100 wallet、完結22,973 episode、BTC 10,125 episode、canonical fills 69,708件を再集計。
- 56% wallet除外とBTC fills上位5 wallet依存72.76%を重大biasとして固定。
- active BTC 5分bucket 7,291件に対するfuture coverageは5分55.85%、60分55.70%。historical OI / asset context / trade stream / wallet stateは0%。
- 9仮説をregistryへ事前登録。H02/H04/H05は導出未実装、H03/H07は部分探索のみ、H01/H06/H08/H09は必要series不足を明示。
- 時間順splitと境界前60分purgeを固定。validation / held-outは閾値選択に使用しない。
- 結論は`NOT_READY_FOR_CONFIRMATORY_BACKTEST`。仮説成績は未算出で、次はexploratory限定のevent/outcome pipeline構築。
- 研究順序を「実データ仮説 → exploratory backtest → 条件・閾値・regime修正 → 再backtest → 別期間・別sampleのout-of-sample検証 → 採否」へ変更。
- synthetic report mockは参考UIとして保持するが、仮説作成・閾値選択・研究判断には使わない。最終レポートは再現性を通過した結果だけで作る。
- 単発の相関、少数sample、同一期間だけの好結果は不採用。有意義な再現性がない仮説は棄却する。
- 次は取得済み実データについて、優先仮説ごとのcoverage・期間・sampling bias・outcome利用可否を監査し、backtest可能範囲を固定する。
- BTC event-study PHASE 2として固定seedの合成120 event / 480 outcomeから期待レポートmockを作成。
- LONG/SHORT集中、entry集中、size/leverage、5/15/30/60分return、逆行率、MFE/MAE、opposite flow、panic exit、明示的liquidationを1つのoffline HTMLで確認可能にした。
- optional coverage不足はleverage/liquidation distance/opposite flowを0埋めせず欠測表示。実測市場row 0と売買判断不可を明記。
- ブラウザで全chart/tableと完成状態を目視確認。PHASE 3はユーザーのmock確認までHOLD。
- BTC event-study PHASE 1として`btc-market-event-v0.1.0`と`btc-post-event-outcome-v0.1.0`を事前登録。
- 1分raw bucketを保持し、連続5分windowを主分析単位、5/15/30/60分をpost-event horizonに固定。
- event featureは`cutoff_ms`以前、outcomeは別file・別namespaceとし、future price/PnL/MFE/MAEのevent table混入を禁止。
- Hoihoi `hoihoi-btc-handoff-v0.1`をversion/hash/quality検証後のみ受け入れる境界を定義。
- core coverageはwallet flow + BTC candle + asset ctx。state/trade/bookはoptional groupとして欠測列だけNULLにする。
- schema契約テスト4件を追加しlocal 61 tests PASS。collector、VPS、実データ収集は未変更。
- BTC event-study PHASE 0として公式API・WebSocket・archiveを棚卸しし、28項目を`取得可能 / forwardなら取得可能 / 取得不能`へ分類。
- walletのposition/leverage/margin/liquidation price/account stateは任意過去へ遡及せず、観測開始後のsnapshotだけを採用する契約を固定。
- BTCのmarket-wide liquidation flowは公式公開APIで直接取得不能とし、観測walletの明示的liquidation eventとは分離。
- 成果物は`design/btc-event-study/data_contract.md`と`field_matrix.csv`。collectorとVPS runtimeは未変更。
- v3のDocker / Compose / systemd service+timer / flock / 19分timeout / structured log / health check / VPS手順を実装。
- collector stateをrun単位transactionへ変更し、endpoint failure・retention・cap時はraw manifestを残してcheckpointを進めない。
- v3専用namespace `forward-data-v3/`、collector version `forward-v3`を固定。
- data branchがdirty、pending push失敗、fast-forward失敗、push conflictの場合は新規runまたは次runへ進まない。
- v3 runtime CIはscheduleを持たず、unit testとDocker buildだけを行う。
- local 61 tests PASS（PHASE 0/1契約テスト6件を追加）。Ubuntu CI run `37173864803`では当時の55 testsとDocker image buildがPASS。

- PHASE 1 GateはPASS。
- PHASE 2はwallet endpoint収集まで完了。OHLCV/BTC seriesは重大再構成差異の停止条件により未実行。
- PHASE 3の実装差異は修正したが、API retentionによる56%除外でGateはFAIL。差異を推定・0埋めで隠していない。
- 500口座拡大はHOLD。
- user-specific WebSocketはIPあたり10 unique users制約のため、固定100口座の正本にしない。定期RESTを正本とする。
- v1 Shadow GateはFAIL。成功run数だけではcoverageを保証できないことを実証した。
- v2の5分cron・shared concurrency・fail-fastは品質問題を正しく検出したが、GitHub scheduled runの実起動遅延を解消できずGate FAIL。
- 次版はGitHub Actions scheduleを正本にせず、20分以内の起動実績を外部から監視できるschedulerが必要。

- TWAP上限2,000件に達し連続性エラー15件が残る1口座を分析対象外とした。
- perp fill 0件の1口座を対象外とした。
- 層別レビューは10口座をすべて含み、勝敗10/10、Long/Short 10/10、反転境界2/2を確認した。
- 非zero builderFeeを含む3サンプルで、builderFeeをfeeへ再加算しないことを確認した。
- 全61episodeでもbuilderFeeを別加算せず、`closedPnl - fee + Funding`がprocessed net PnLと一致した。
- 旧`account_quality.csv`はperp fill 0口座のstored eligible flagが1件だけ古い。今回と現行コードは再計算条件で正しく除外しており、次回PoC再生成時にキャッシュを更新する。
- 養分行動分類はまだ開始していない。
- 公式candleの直近5,000本制限により、37episodeはentry前60分の5分足が0/12でNOT_READY。
- PARTIAL 24episodeはpast-onlyのprice return／volume特徴量だけ許容する。mark/OI/Funding依存特徴量へ暗黙利用しない。
- entry足、exit時刻、PnL、MFE/MAE、post-entry candleは特徴量計算interfaceから物理的に除外した。
- 24件は特徴量パイプラインのPoCとして使用可能だが、行動別成績や「逆指標」の統計結論には少なすぎる。
- label config v1.0.0はdry-run後に固定。閾値変更はv1上書きではなくv2を作る。
- FOMO/Late重複はschema上許可しsynthetic test済みだが、今回の24件では重複0。
- 個別addのpre-add平均・add価格・stable order traceがdry-run成果物に未保存。100口座pilot前の監査証跡追加が必要。

## Tests

- `python3 -m unittest discover -s tests -v`
- 91 tests passed
- 専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN` を使用。
- Discord 403は解消済み。
- 最終成功通知run: `36956495550`。

## Known Limitations

- 現在の建玉・レバレッジ設定・清算価格は直接取得可能だが、任意の過去cross-margin状態と清算直前equityは正確な復元が困難。
- candleは直近5,000本、5分足で約17日。
- leaderboardには高頻度whale、spot中心、期間内無活動口座が混ざる。
- 清算0件は存在しないという意味ではなく、今回の標本では未観測。
- REST APIにはweight-based rate limitがある。
- TWAP endpoint上限到達口座は完全な履歴を取得できず、行動分析対象外。

## Passed Gate

完結61episodeの全件自動照合と、20episodeの層別目視レビューで重大差異0。

成果物: `reviews/episode-quality-2026-10-02/README.md` と `episode_review.csv`。

会計照合は61/61 PASS、二重計上0、重大差異0。

成果物: `reviews/accounting-quality-2026-10-02/`。

## Next

24時間canary用の公式WebSocket / REST adapterとVPS配置へ進むには外部操作が必要。ユーザーが配置先を決めるまで停止する。
