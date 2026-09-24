# Hyperliquid Trade Risk Bot / Wallet Report Bot

Hyperliquidの自分のウォレットを読み取り、Discord向けに次の通知を作るBotです。

- 即時リスク通知: 危険ポジションだけ短く通知
- デイリーレポート: 23:00 JST締め、23:30 JST通知
- ウィークリーレポート: 日曜22:00 JST通知

売買や資金移動は行いません。秘密情報は `.env` または GitHub Secrets に置き、コードには書きません。

## 今回追加した本人行動リスク監視

公開ウォレットだけを読み、個々の約定をSQLiteへ重複なく保存します。`startPosition` と
`side` から銘柄別のゼロ→ゼロを1つのposition cycleとして再構成し、部分約定、追加、
部分決済、Long/Short反転を区別します。秘密鍵・署名・exchange endpointは使いません。

検知種別は次の10種です。

- `SIZE_UP_AFTER_WIN`: 勝ち後に次の最大建玉が1.5倍以上
- `REVENGE_TRADE`: 損失終了から30分以内の同一銘柄再エントリー（反転はCRITICAL）
- `LOSS_AVERAGING`: 含み損方向への追加
- `PROFIT_PYRAMIDING`: 大幅含み益中の急な追加
- `DAILY_PROFIT_GIVEBACK`: 当日ピーク利益の30/50/70%吐き出し
- `PEAK_DRAWDOWN`: 当日ピークから5/8/10/15%ドローダウン
- `SAME_COIN_OVERTRADE`: 2時間以内に同一銘柄へ5回以上
- `CONSECUTIVE_LOSSES`: 2/3/4連敗
- `LIQUIDATION_TOO_CLOSE`: 清算まで5/3/1.5%未満
- `OVERSIZED_POSITION`: 価格1%変動で資産の5/8/10%以上

DBには既存の `fills` / `snapshots` / `positions` を維持したまま、`trades`、
`daily_stats`、`risk_events`、`bot_state` を自動追加します。既存DBは破壊せず移行されます。
MAE/MFE列は用意済みですが、過去区間の十分な価格系列がないcycleはNULLのまま保存します。

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

リアルタイム監視はMacで60秒おきに実行するのを推奨します。まず手動dry-runを確認し、
`.env` の `DRY_RUN=false` は文面と通知先を確認してから設定してください。

```bash
cd ~/base-lab/projects/hyperliquid-wallet-report-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m src.main risk --dry-run
```

launchdでは `scripts/com.base-lab.hyperliquid-risk.plist.example` 内の2つの絶対パスを
自分の環境に合わせ、`~/Library/LaunchAgents/` へコピーして `launchctl bootstrap` します。
テンプレートは60秒周期で1回実行し、プロセス常駐や秘密値のplist埋め込みをしません。

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

ActionsはGitHubのschedule遅延があるためリアルタイム監視の主系にはしません。既存どおり
毎時の補助監視だけです。daily/weeklyの自動通知は別の `hyperliquid-report` リポジトリが
正本であり、このworkflowからは二重送信しません。

## 設定

実行時設定は既存設計との互換性のため環境変数を正本にしています。`config.yaml` は閾値の
一覧表です。主な対応は以下です。

| 環境変数 | 初期値 |
|---|---:|
| `MAX_LOSS_PER_TRADE` | 30 |
| `MAX_DAILY_LOSS` | 60 |
| `SIZE_UP_MULTIPLIER` | 1.5 |
| `REVENGE_TRADE_MINUTES` | 30 |
| `SAME_COIN_WINDOW_MINUTES` | 120 |
| `SAME_COIN_TRADE_COUNT` | 5 |
| `RISK_COOLDOWN_MINUTES` | 15 |

同じリスク種別＋銘柄はcooldown中に抑制し、段階が悪化した場合は即時再通知します。
`.env` とSQLite (`.state/`) はgit管理外です。

## テスト

```bash
PYTHONPATH="$PWD/../.." python3 -m unittest discover -s tests -v
python3 -m src.main risk --sample --dry-run --db-path /tmp/trading-risk.sqlite
```

テストは追加・部分決済・全決済・Long→Short・Short→Long・tid重複・DB再起動・
`300→550→920→250` のピークDD 72.8%を含みます。API/Discordのtimeoutは共有クライアントの
既存retry・最終例外処理をそのまま使用します。

Webhookだけ確認する場合は、Actionsの手動実行で `mode=discord-test`, `dry_run=false` を選びます。
