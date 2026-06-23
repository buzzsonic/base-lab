# base-lab

暗号通貨市場の調査、分析、検知ボットを置くための作業リポジトリです。

## projects

- `projects/hyperliquid-leaderboard-alert/`
  - Hyperliquidのリーダーボード関連情報をもとに、大きな現在ポジションをDiscordへ通知するGitHub Actionsバッチです。

- `projects/hyperliquid-wallet-report-bot/`
  - 自分のHyperliquidウォレットを監視し、即時リスク通知、デイリー/ウィークリーレポートをDiscordへ通知するGitHub Actionsバッチです。

## secrets

APIキーやWebhook URLなどの秘密情報はコミットしません。GitHub ActionsではRepository Secretsを使います。
