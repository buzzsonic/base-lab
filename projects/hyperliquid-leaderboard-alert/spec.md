# Hyperliquidリーダーボード検知ボット 仕様

## 目的

Hyperliquidのリーダーボード関連情報から勝ちウォレット・負けウォレットを取得し、各ウォレットの現在ポジションをHyperliquid APIで確認する。条件に合う大きなポジションがあればDiscordへ通知する。

## 検知対象

- 勝ちウォレット、負けウォレットの現在オープンポジション
- `MIN_ABS_POSITION_USD` 以上のUSD換算ポジション
- `TARGET_SIDE` が `long` の場合はロングのみ
- `TARGET_SIDE` が `short` の場合はショートのみ
- `TARGET_SIDE` が `both` の場合はロングとショートの両方

初期版は前回状態との差分ではなく、実行時点のスナップショット通知とする。

## 実行方式

- GitHub Actionsで30分ごとに起動する
- cronは `*/30 * * * *`
- 手動実行は `workflow_dispatch`
- 常駐処理ではなく、1回起動してチェックし、必要なら通知して終了する
- Python 3.11で `python -m src.main` を実行する

## 通知仕様

Discord通知は日本語で送信する。通知には次を含める。

- タイトル
- 実行時刻 JST
- 対象ウォレット
- 勝ちウォレット/負けウォレットの区分
- 銘柄
- ロング/ショート
- ポジションサイズ
- エントリー価格
- 未実現損益
- 清算価格
- レバレッジ

Discordの文字数制限を避けるため、通知本文は上位数件に絞る。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_WEBHOOK_URL` | 必須 | Discord Webhook URL。GitHub ActionsではSecretsから読み込む |
| `ALERT_MODE` | 任意 | 初期版は `leaderboard` のみ |
| `LEADERBOARD_LIMIT` | 任意 | 勝ち/負けそれぞれの取得件数 |
| `TARGET_SIDE` | 任意 | `both`, `long`, `short` |
| `MIN_ABS_POSITION_USD` | 任意 | 通知対象にする最低ポジションUSD換算 |
| `MIN_POSITION_CHANGE_USD` | 任意 | 将来の差分検知用。初期版では未使用 |
| `DRY_RUN` | 任意 | `true` の場合はDiscord送信せずログに出す |

## 将来拡張

- GitHub Actions artifact、cache、外部ストレージのいずれかで前回スナップショットを保存する
- `MIN_POSITION_CHANGE_USD` を使った増減検知を追加する
- ウォレット分類をDexly以外の信頼できるデータソースでも検証する
- Discord通知を銘柄別、ウォレット別に集約する
- APIレート制限に応じた取得件数制御を追加する
