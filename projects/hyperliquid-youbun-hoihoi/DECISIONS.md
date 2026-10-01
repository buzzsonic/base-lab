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
