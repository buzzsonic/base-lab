# Hyperliquid Wallet Report Bot

Hyperliquidの自分のウォレットを読み取り、Discord向けに次の通知を作るBotです。

- 即時リスク通知: 危険ポジションだけ短く通知
- デイリーレポート: 23:00 JST締め、23:30 JST通知
- ウィークリーレポート: 日曜22:00 JST通知

売買や資金移動は行いません。秘密情報は `.env` または GitHub Secrets に置き、コードには書きません。

## 決定済みの通知方針

### デイリー

- 100点満点で厳しめ
- 配点: PnL 50 / リスク・行動 50
- 50点未満は警告トーン
- 数字・集計・現在ポジション判断・減点項目・明日のルールを中心にする
- 「今日の傾向」「良かった点」「悪かった点」は入れない
- 明日のルールは最大3個
- 未決済ポジションの含み損益は表示するが、点数には控えめに反映

### ウィークリー

- 100点満点
- 配点: PnL 40 / 再現性 30 / リスク管理 30
- 勝ちパターン、負けパターン、銘柄別、来週のルールを出す

### 即時リスク通知

- 同じポジション・同じ危険理由は1時間に1回まで
- 清算距離がさらに悪化した場合は再通知
- ポジションが変わったら即通知

強い警告の初期基準:

- 清算距離5%未満
- ストップなし
- 口座比6倍以上
- 証拠金使用率90%以上
- 利確後すぐ逆方向エントリー
- 1日の手数料が利益の30%以上
- 日次実現損益が口座の-5%以上

## ローカル実行

```bash
cd projects/hyperliquid-wallet-report-bot
cp .env.example .env
python3 -m src.main risk --dry-run
python3 -m src.main daily --dry-run
python3 -m src.main weekly --dry-run
python3 -m src.main discord-test --dry-run
```

サンプルデータだけで文面を見る場合:

```bash
python3 -m src.main daily --sample --dry-run --db-path /tmp/hyperliquid-wallet-report-bot.sqlite --reports-dir /tmp/hyperliquid-wallet-reports
python3 -m src.main weekly --sample --dry-run --db-path /tmp/hyperliquid-wallet-report-bot.sqlite --reports-dir /tmp/hyperliquid-wallet-reports
```

## GitHub Actions

`.github/workflows/hyperliquid-wallet-report-bot.yml` が以下を実行します。

- 毎時: 即時リスク通知
- 23:30 JST: デイリーレポート
- 日曜22:00 JST: ウィークリーレポート

GitHub Secrets:

- `DISCORD_WEBHOOK_URL`: 既存Botと同じSecret名を使います。
- `HYPERLIQUID_WALLET_ADDRESS`: 任意。未設定なら既存の監視対象ウォレット `0x5544C446E589fccB0d0B730e6289a22d967E6910` を使います。

最初は `DRY_RUN=true` で確認し、文面が納得できてから `false` にしてください。

Webhookだけ確認する場合は、Actionsの手動実行で `mode=discord-test`, `dry_run=false` を選びます。
