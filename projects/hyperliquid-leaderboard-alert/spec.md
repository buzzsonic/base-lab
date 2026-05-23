# Hyperliquidリーダーボード検知ボット 仕様

## 目的

Hyperliquidのリーダーボード関連情報から勝ちウォレット・負けウォレットを取得し、各ウォレットの現在ポジションをHyperliquid APIで確認する。勝ち/負け、現在/新規/増加、銘柄、方向ごとに集計してDiscordへ通知する。

## 検知対象

- 勝ちウォレット、負けウォレットの現在オープンポジション
- `MIN_ABS_POSITION_USD` 以上のUSD換算ポジション
- `TARGET_SIDE` が `long` の場合はロングのみ
- `TARGET_SIDE` が `short` の場合はショートのみ
- `TARGET_SIDE` が `both` の場合はロングとショートの両方

現在ポジションは実行時点のスナップショットを集計する。新規ポジションと増加ポジションは、前回実行時の `.state/leaderboard_snapshot.json` と比較して判定する。GitHub Actionsではこの `.state` ディレクトリをActions cacheで復元・保存する。

新規ポジション:

- 前回スナップショットに同じ `ウォレット + 銘柄 + 方向` がない
- 今回のポジションUSD換算が `MIN_POSITION_CHANGE_USD` 以上
- ウォレットが新しく勝ち/負けランキング対象に入った場合、そのウォレットの既存ポジションも新規扱いになる可能性がある

増加ポジション:

- 前回スナップショットに同じ `ウォレット + 銘柄 + 方向` がある
- ポジション数量が増えている
- 増加数量を現在価格で換算した金額が `MIN_POSITION_CHANGE_USD` 以上

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
- 勝ちウォレット/負けウォレットの区分別サマリー
- 銘柄
- ロング/ショート
- 現在ポジション合計
- 新規ポジション合計
- 増加ポジション合計
- サイズ加重平均Entry価格
- 現在価格
- ウォレット数
- 未実現損益合計

Discordの文字数制限を避けるため、個別ウォレットの羅列は行わず、集計上位だけを表示する。

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_WEBHOOK_URL` | 必須 | Discord Webhook URL。GitHub ActionsではSecretsから読み込む |
| `ALERT_MODE` | 任意 | 初期版は `leaderboard` のみ |
| `LEADERBOARD_LIMIT` | 任意 | 勝ち/負けそれぞれの取得件数 |
| `TARGET_SIDE` | 任意 | `both`, `long`, `short` |
| `MIN_ABS_POSITION_USD` | 任意 | 通知対象にする最低ポジションUSD換算 |
| `MIN_POSITION_CHANGE_USD` | 任意 | 新規・増加として通知対象にする最低USD換算 |
| `DRY_RUN` | 任意 | `true` の場合はDiscord送信せずログに出す |

## 将来拡張

- Actions cache以外の永続ストレージ対応
- `userFillsByTime` を使った実約定ベースの新規価格取得
- ウォレット分類をDexly以外の信頼できるデータソースでも検証する
- Discord通知を銘柄別、ウォレット別に集約する
- APIレート制限に応じた取得件数制御を追加する
