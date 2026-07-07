# base-lab

暗号通貨市場の調査、分析、検知ボットを置くための作業リポジトリです。

## shared

`shared/` は全プロジェクト共通のライブラリです。

- `shared/hyperliquid.py` — Hyperliquid Info APIクライアント（リトライ、429対応込み）
- `shared/discord.py` — Discord Webhook送信（テキスト/embed、リトライ込み）
- `shared/envtools.py` — 環境変数の読み込みヘルパー
- `shared/logging_utils.py` — JSTタイムスタンプ付きロガー

各プロジェクトはリポジトリルートを `PYTHONPATH` に載せて実行します。
GitHub Actionsでは `PYTHONPATH: ${{ github.workspace }}` を設定済みです。
ローカルで動かす場合:

```sh
cd projects/<project-name>
PYTHONPATH=../.. DRY_RUN=true python -m src.main
```

## projects

- `projects/hyperliquid-leaderboard-alert/`
  - Hyperliquidのリーダーボード関連情報をもとに、大きな現在ポジションをDiscordへ通知するGitHub Actionsバッチです。

- `projects/hyperliquid-wallet-report-bot/`
  - 自分のHyperliquidウォレットを監視し、即時リスク通知、デイリー/ウィークリーレポートをDiscordへ通知するGitHub Actionsバッチです。

- `projects/coin-scout/`
  - 「狙い目コイン」のスクリーニングボット。Hyperliquid上場×CEX出来高$10M+の銘柄を対象に、出来高急増・ファンディング/OIの偏り・新規上場を検知して1日2回(8時/20時JST)Discordへ通知します。

## secrets

APIキーやWebhook URLなどの秘密情報はコミットしません。GitHub ActionsではRepository Secretsを使います。
