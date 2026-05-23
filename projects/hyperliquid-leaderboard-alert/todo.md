# todo

## 初期実装

- [x] GitHub Actionsで30分ごとに起動するバッチ型workflowを作成
- [x] 環境変数読み込みと型変換を実装
- [x] Hyperliquid `info` endpoint用POSTクライアントを実装
- [x] Dexly公開リーダーボードから勝ち/負けウォレット候補を取得
- [x] `clearinghouseState` から現在ポジションを取得
- [x] 大きなポジションを検知してDiscord通知する
- [x] 勝ち/負けウォレット別、現在/新規/増加別の集計通知に変更
- [x] GitHub Actions cacheで前回スナップショットを保存・復元

## 動作確認

- [ ] GitHub Secretsに `DISCORD_WEBHOOK_URL` を登録
- [ ] Actionsの手動実行で成功することを確認
- [ ] Discordに通知が届くことを確認
- [x] `DRY_RUN=true` で送信せずログ出力できることを確認

## 差分検知

- [x] 前回スナップショットの保存先を決める
- [x] GitHub Actions cacheで前回結果を復元する
- [ ] 外部DBまたはCloudflare KVなどの軽量ストレージ利用を検討する
- [x] `MIN_POSITION_CHANGE_USD` 以上の増加だけ通知する
- [ ] 初回実行時は「初回基準」として保存のみ行うモードを検討する

## ウォレット分類精度向上

- [ ] Hyperliquid公式APIでリーダーボード相当の取得方法があるか継続確認
- [ ] Dexly HTML構造変更時の検知を追加する
- [ ] 勝ち/負けウォレットの期間を `day`, `week`, `month` で切り替え可能にする
- [ ] HFTウォレットや非アクティブウォレットを除外する設定を追加する

## 通知文改善

- [x] 銘柄別に集約したサマリーを追加する
- [x] 同一ウォレットの複数ポジションをまとめる
- [ ] 清算価格が近いポジションを優先表示する
- [ ] Discord embed形式への移行を検討する

## GitHub Actions安定運用

- [ ] APIレート制限時のバックオフを強化する
- [ ] 取得失敗が多い場合に警告通知する
- [ ] Actionsの実行時間が長くなった場合に `LEADERBOARD_LIMIT` を調整する
- [ ] 依存ライブラリの更新を定期確認する
