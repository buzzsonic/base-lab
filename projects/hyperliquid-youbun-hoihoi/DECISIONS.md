# DECISIONS

## 2026-10-01 養分くんから完全分離

- 決定: `projects/hyperliquid-youbun-hoihoi`を独立entrypoint/data contractとする。
- 理由: 対象選定と行動ラベルを分け、selection leakageを防ぐ。
- 影響: 養分くん既存ファイルは変更しない。
- 未解決: sample受け渡しの自動同期は7日後promotionまで保留。

## 2026-10-01 初回sampleを無理に埋めない

- 決定: first_seen当日のcandidateは全件OBSERVINGで、research sampleは0件を許容する。
- 理由: 「約1週間観察」を実データなしで偽装しないため。
- 影響: 初回成果物はschema付き空Parquetになりうる。
- 未解決: 7日間の日次activity coverageを何回必要とするか。

## 2026-10-01 勝敗非参照の二経路PoC

- 決定: official leaderboard層別とpublic Trades時点抽出を50:50で混合する。
- 理由: leaderboard単独とPnL選抜を避ける。
- 影響: live TradesはMM/activity biasを持つため、BOT/MM比率を明示する。
- 未解決: node fillsの増分取り込み費用とActions実行時間。

## 2026-10-01 Issue #8 層化抽出へ変更

- 決定: 公開Tradesの先着抽出と固定50/50採用をやめ、200-wallet discovery poolから頻度・規模・銘柄傾向・順位帯・時間帯・活動日数の不足層を優先して100件を選ぶ。
- 理由: 旧PoCは高頻度67%、BOT疑い52%、fills cap 84%でactivity/bot biasが強すぎた。
- 影響: 高頻度48%、BOT疑い38%、cap 63%へ改善。未選抜poolは`discovery_pool.parquet`に保持する。
- 未解決: 小型アルト中心は2件、capは63%残るため、1,000件拡大は保留する。

## 2026-10-01 小型アルトproxy

- 決定: 公式`metaAndAssetCtxs.dayNtlVlm`が1,000万USDC未満の非BTC/ETH銘柄を小型アルトproxyとし、50%以上の取引notionalを占めるwalletを小型アルト中心とする。閾値は設定可能にする。
- 理由: 時価総額の公式履歴は取得できず、現在の市場流動性を再現可能な公開proxyとして使うため。
- 影響: 小型アルト分類は市場状況で変化し、過去時点の厳密な時価総額分類ではない。
- 未解決: `metaAndAssetCtxs`のsnapshot versionをsample versionへ固定する。

## 2026-10-02 Issue #8 完了通知

- 決定: Issue #8 の層化再PoCを `main@91a873b` へ反映し、養分ホイホイ専用Discord webhookで完了通知する。
- 実績: GitHub Actions run `36928323512` の送信jobはsuccess。
- 影響: Issue #8の品質改善は完了扱いとするが、1,000-wallet拡大のHOLD判断は維持する。

## 2026-10-02 増分取得と観察証拠

- 決定: first_seenから7日以上経過し、7 JST日の完全な取得成功を確認したwalletだけをACTIVEにする。過去約定の活動日数は観察成功日数の代用にしない。
- 決定: BOT/MM/farm/裁定疑いはregistryから削除せずEXCLUDEDとし、通常sampleへ入れない。
- 決定: userFillsByTimeの2,000件応答を時間分割して解消し、同一ms飽和・budget不足・10,000件retention到達は取得欠損として保持する。
- 制約: 公開APIだけでは10,000件より古い履歴を復元できない。未解決gapがlookback外になるまで完全性を回復したと扱わない。
- 決定: 未統合のcodex/hoihoi-public-trades-collector実装を再利用し、市場snapshot保存とdata branch保存を追加する。
- 未解決: 実APIとActionsでの保存検証、実測改善、サンプル全体の品質ゲート、snapshot/weekly実装。

## 2026-10-03 新100件は隔離観察してから判断

- 決定: fresh 200→100再PoCの結果は採用候補として保存するが、現行registry 100件を即時置換しない。
- 証拠: run 37116104107で履歴不完全21→2、small-alt 0→9、BOT疑い39→29、MM疑い12→4へ改善。現行との重複42件。20件レビューで閾値不一致0件。
- 理由: 新cohortの成功観察日は完全取得98件が1日、欠損2件が0日で、7日・7 JST日分のpromotion gateを満たさない。MM/farmラベルも公開約定だけでは戦略確定できない。
- 影響: 次は別cohortとして7日追跡し、既存観察を維持したまま比較する。1,000-wallet拡大はHOLD。

## 2026-10-03 data branch競合はrebase再試行

- 決定: discovery/observationのdata branch pushは最大3回、失敗時にfetch・rebaseして再試行する。force pushは禁止。
- 理由: run 37081829753は収集とartifact生成が成功した一方、並行workflowの更新でnon-fast-forwardとなり保存だけ失敗した。
- 証拠: PR #25統合後の収集run 37116093295、観察run 37116402104、snapshot run 37116871931はすべてsuccess。

## 2026-10-03 shadow cohortを別namespaceで観察

- 決定: 新100件は`outputs/cohorts/stratified-20261003/`に固定し、現行`outputs/current/`とregistry、pool、checkpoint、cache、sampleを共有しない。
- 決定: 毎日03:20 JSTに同じdata branch排他ロックで観察する。seed欠落時は現行cohortへフォールバックせず失敗させる。
- 理由: 改善候補を7日評価しながら、観察2日目の現行100件を破壊・置換しないため。
- 影響: 7日後の比較と明示判断なしにcohortの置換・統合・1,000件拡大は行わない。

## 2026-10-04 weeklyは比較報告のみ

- 決定: weekly workflowは現行・shadowのregistry/pool/sampleを読み、構造、履歴完全性、成功JST日、flag、small-alt、ACTIVE/sample一致をJSON化する。
- 決定: registryとsampleは変更せず、出力は`outputs/reports/weekly/YYYY-MM-DD/cohort_comparison.json`だけに限定する。
- 決定: 全gate通過後も結果は`READY_FOR_HUMAN_REVIEW`までとし、置換・統合・通知・売買は自動化しない。
- 理由: 日次promotionとcohort採否を分離し、欠測やsample不一致を隠さず人が比較判断できるようにするため。

## 2026-10-04 weekly reportをJST日付・専用queueへ分離

- 決定: report保存日は`Asia/Tokyo`の暦日とし、weeklyは`youbun-hoihoi-weekly`専用concurrency groupを使う。
- 理由: 初回runはUTC日付へ保存され、共有data queueでは新しいpending collectorにweeklyが取り消され得たため。
- 安全境界: weeklyはcohort stateを変更せず、日付付きreportだけを追加する。data branch競合はforce pushせずrebase再試行で解決する。
- 証拠: PR #35統合後のrun 37172824334はsuccess、data `1b7786e`はJST `2026-10-04`のreport 1ファイルだけを追加した。

## 2026-10-04 BTC研究sample契約をdry-run前に固定

- 決定: v0.1 draftの最低Gateを7成功JST日、BTC 3活動日、20 fills、5完結zero-to-zero episode、profile根拠3 episodeとする。
- 決定: BOT / MM / arbitrage / funding arbitrage / farm疑い、未解消gap、continuity error、quantity mismatch、page/TWAP capはfail-closedで除外する。
- 決定: add行動の存在自体は必須にしない。完全なordered fillsからadd 0を観測できればよい。存在を必須化するとナンピンwalletを選抜段階で過剰抽出するため。
- 決定: 高値飛び乗りは養分くんのpast-only FOMO定義、ナンピンは5% size・5bp adverse定義を再利用する。size急拡大は直前5 BTC episode中央値の2倍をdraft初期値とする。
- 決定: handoffにPnL、勝率、ROI、entry後return、markout、MFE/MAEを含めず、市場反応を見てwalletを選ばない。
- 影響: v0.1はdry-run前draft。結果を見て同versionを調整せず、変更時は新versionを作る。1,000-wallet拡大は非優先HOLD。
