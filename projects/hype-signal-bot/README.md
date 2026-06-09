# HYPE Signal Bot

Hyperliquid の HYPE を監視し、Discord にシグナルを通知する GitHub Actions 用 Bot です。

## ファイル階層

```text
projects/hype-signal-bot/
  requirements.txt
  .env.example
  src/
    fetcher.py
    signals.py
    notifier.py
    state.py
    main_scalp.py
    main_swing.py
.github/workflows/hype-signal-bot.yml
```

## GitHub Secrets

`Settings` -> `Secrets and variables` -> `Actions` に次を登録します。

| Name | Value |
| --- | --- |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |

## 自動実行

- スキャル: 5分ごと
- スイング: 4時間ごと
- 手動実行: GitHub Actions の `workflow_dispatch`
- シグナルなしの場合も、スキャル監視が1時間に1回Discordへ稼働通知します。

GitHub Actions の cron は厳密な分単位実行を保証しません。通知が止まったように見える場合は、まず Actions の実行履歴で「workflow が起動しているか」と「起動したが通知対象なしだったか」を分けて確認してください。

## ローカル実行

```bash
cd projects/hype-signal-bot
python -m pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python -m src.main_scalp
python -m src.main_swing
```
