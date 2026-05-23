# Hyperliquidリーダーボード検知ボット

## 目的

Hyperliquidのリーダーボード関連情報から勝ちウォレット・負けウォレットを取得し、現在のポジションを確認する検知ボットです。勝ちウォレット・負けウォレットごとに、現在ポジション、新規ポジション、増加ポジションを集計してDiscordへ日本語で通知します。

このボットは売買を実行しません。30分ごとにGitHub Actions上で1回だけ起動し、チェックと通知を行って終了するバッチ型です。MacやローカルPCが停止していても、GitHub Actionsが有効なら実行されます。

## GitHub Actionsでの動かし方

`.github/workflows/hyperliquid-leaderboard-alert.yml` が30分ごとの自動実行と手動実行に対応しています。

実行内容:

1. リポジトリをcheckout
2. Python 3.11をセットアップ
3. `projects/hyperliquid-leaderboard-alert/requirements.txt` をインストール
4. 前回スナップショットをGitHub Actions cacheから復元
5. `projects/hyperliquid-leaderboard-alert` をworking directoryにして `python -m src.main` を実行
6. 今回スナップショットをGitHub Actions cacheへ保存

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
| `MIN_POSITION_CHANGE_USD` | `500000` | 新規・増加として通知対象にする最低USD換算 |
| `DRY_RUN` | `false` | `true` の場合はDiscord送信せずログ出力だけ行う |

## 通知の見方

Discord通知は個別ウォレットを1件ずつ並べず、次の形で集計します。

```text
■ 勝ちウォレット 現在ポジ
HYPE LONG $75.8M / Entry $38.68 / 現在 $54.94 / 4ウォレット / PnL +$22.4M

■ 勝ちウォレット 新規ポジ
ETH SHORT 新規 $3.5M / Entry $2,240 / 2ウォレット

■ 勝ちウォレット 増加ポジ
BTC LONG 増加 +$1.2M / 推定Entry $74,900 / 1ウォレット
```

- `Entry` はサイズ加重平均Entry価格です
- `現在` はHyperliquid `allMids` の現在価格です
- `ウォレット` は該当ポジションを持つウォレット数です
- `増加` の `推定Entry` は、前回と今回の平均Entryと数量差から推定した増加分の価格です

## 現時点の制限

- Hyperliquid公式Info APIには、現時点でリーダーボードを直接返す明確なendpointを確認できていません。
- 初期版ではDexlyの公開リーダーボードページからウォレット候補を解析します。Dexly側のHTML構造が変わると取得できなくなる可能性があります。
- Hyperliquid APIで確認するのは `clearinghouseState` による現在ポジションです。
- 新規・増加は前回スナップショットとの差分です。初回実行では前回データがないため、次回から判定されます。
- Actions cacheは永続DBではないため、cacheが消えた場合は再び初回扱いになります。
- ウォレットが新しく勝ち/負けランキング対象に入った場合、そのウォレットの既存ポジションも「新規」として出る可能性があります。
- `clearinghouseState` だけでは正確な約定時刻や実約定単価までは分かりません。増加分のEntryは推定値です。
- Discordの文字数制限を避けるため、通知は集計上位だけに絞ります。

## 今後の改善案

- 外部DBなどを使ったより安定した前回スナップショット保存
- `userFillsByTime` を使った実約定ベースの新規・増加価格取得
- 銘柄別サマリー、ウォレット別サマリーの追加
- 清算価格が近いポジションの優先通知
- Hyperliquid公式APIでリーダーボード相当の取得方法が確認できた場合の置き換え
- API失敗率が高い場合の警告通知
