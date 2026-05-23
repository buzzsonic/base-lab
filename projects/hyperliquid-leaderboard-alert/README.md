# Hyperliquidリーダーボード検知ボット

## 目的

Hyperliquidのリーダーボード関連情報から勝ちウォレット・負けウォレットを取得し、現在のポジションを確認する検知ボットです。大きなポジションを持っているウォレットがあればDiscordへ日本語で通知します。

このボットは売買を実行しません。30分ごとにGitHub Actions上で1回だけ起動し、チェックと通知を行って終了するバッチ型です。MacやローカルPCが停止していても、GitHub Actionsが有効なら実行されます。

## GitHub Actionsでの動かし方

`.github/workflows/hyperliquid-leaderboard-alert.yml` が30分ごとの自動実行と手動実行に対応しています。

実行内容:

1. リポジトリをcheckout
2. Python 3.11をセットアップ
3. `projects/hyperliquid-leaderboard-alert/requirements.txt` をインストール
4. `projects/hyperliquid-leaderboard-alert` をworking directoryにして `python -m src.main` を実行

## GitHub Secretsの登録手順

1. GitHubリポジトリを開く
2. `Settings` を開く
3. `Secrets and variables` -> `Actions` を開く
4. `New repository secret` を押す
5. Nameに `DISCORD_WEBHOOK_URL` を入力
6. SecretにDiscord Webhook URLを入力
7. `Add secret` で保存

Webhook URLは `.env.example` やコードに直接書かないでください。

## 手動実行の方法

1. GitHubリポジトリの `Actions` タブを開く
2. `Hyperliquid Leaderboard Alert` を選ぶ
3. `Run workflow` を押す
4. 実行ログとDiscord通知を確認する

## 30分ごとの自動実行

workflowのcronは次の設定です。

```yaml
schedule:
  - cron: "*/30 * * * *"
```

GitHub ActionsのscheduleはUTC基準で動きます。また、GitHub側の混雑状況により実行開始が数分遅れることがあります。

## ローカル実行方法

```bash
cd projects/hyperliquid-leaderboard-alert
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.main
```

ローカル実行時は `.env` に `DISCORD_WEBHOOK_URL` を設定してください。送信したくない場合は `DRY_RUN=true` にします。

## .env の説明

| 変数 | 初期値 | 説明 |
| --- | --- | --- |
| `DISCORD_WEBHOOK_URL` | 空 | Discord Webhook URL。GitHub ActionsではSecretsから読み込む |
| `ALERT_MODE` | `leaderboard` | 初期版は `leaderboard` のみ対応 |
| `LEADERBOARD_LIMIT` | `100` | 勝ち/負けそれぞれの取得件数 |
| `TARGET_SIDE` | `both` | `both`, `long`, `short` |
| `MIN_ABS_POSITION_USD` | `10000` | 通知対象にする最低ポジションUSD換算 |
| `MIN_POSITION_CHANGE_USD` | `5000` | 将来の差分検知用。初期版では未使用 |
| `DRY_RUN` | `false` | `true` の場合はDiscord送信せずログ出力だけ行う |

## 現時点の制限

- Hyperliquid公式Info APIには、現時点でリーダーボードを直接返す明確なendpointを確認できていません。
- 初期版ではDexlyの公開リーダーボードページからウォレット候補を解析します。Dexly側のHTML構造が変わると取得できなくなる可能性があります。
- Hyperliquid APIで確認するのは `clearinghouseState` による現在ポジションです。
- GitHub Actionsでは前回状態の永続保存が標準では扱いづらいため、初期版は差分通知ではなく現在状態のスナップショット通知です。
- `MIN_POSITION_CHANGE_USD` は将来の差分検知用で、初期版では判定に使っていません。
- Discordの文字数制限を避けるため、通知はポジションサイズ上位数件に絞ります。

## 今後の改善案

- GitHub Actions artifact、cache、外部DBなどを使った前回スナップショット保存
- `MIN_POSITION_CHANGE_USD` を使ったポジション増減検知
- 銘柄別サマリー、ウォレット別サマリーの追加
- 清算価格が近いポジションの優先通知
- Hyperliquid公式APIでリーダーボード相当の取得方法が確認できた場合の置き換え
- API失敗率が高い場合の警告通知
