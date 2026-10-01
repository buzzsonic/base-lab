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
- 未解決事項: main反映後のworkflow成功とDiscord受信確認。
