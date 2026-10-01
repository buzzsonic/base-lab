# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

## 0. Discord Webhook更新と実送信確認

- 目的: GitHub共有運用とpush後通知を有効にする。
- 作業: Discordの `HTTP 403 Forbidden` 対策として明示的なUser-Agentを付けて再送し、失敗時のみWebhookを再発行・更新する。
- 完了条件: workflow run成功、Discord受信確認。Webhook値は表示・保存しない。
- 現状: PR #4で専用Secret参照へ切替済み。PR #5後のrun `36873349619`で `HTTP 403 Forbidden` と判明。

## 1. 完結61episodeの層別目視検証

- 目的: 再構成が行動ラベルの土台として正しいことを確認する。
- 作業: 勝敗、Long/Short、追加、部分決済、反転、保有時間、fill数で層別し、原fillとepisodeを並べた匿名化レビュー表を作る。
- 完了条件: 選定方法、確認件数、差異、除外理由を記録し、重大差異0または修正・再検証済み。
- テスト: entry/exit数量、closedPnl、fee、Funding、時刻順序をrawと照合する。

## 2. TWAP / Funding / builder feeの会計照合を完成

- 目的: episode純損益と費用の二重計上・欠落を防ぐ。
- 作業: TWAP統合、Funding時間窓帰属、`fee`と`builderFee`の関係をサンプルで確認する。
- 完了条件: 対象episodeで数量・PnL・fee差分が許容誤差内。TWAP上限口座は明示除外。
- テスト: fixtureと実データreconciliation表。

## 3. 5分市場系列coverage確認

- 目的: episode特徴量を計算できる期間を確定する。
- 作業: coin/time別にOHLCV、mark、OI、Fundingの必要窓と実取得窓を比較する。
- 完了条件: coverage率と欠測理由をepisodeごとに保存する。
- テスト: coverage不足では特徴量が0ではなくNULLになること。

## 4. 市場特徴量付与

品質ゲート通過episodeだけにpast-only特徴量を付与する。未来情報をentryラベルへ使用しない。

## 後続（まだ開始しない）

FOMO、Late Long/Short、ナンピン、Revenge、Trapped、crowding分類。品質ゲート通過前に「負ける」「逆指標」と結論づけない。

## 作業終了時

`CURRENT_STATUS.md`と本ファイルを更新し、必要なら`DECISIONS.md`へ追記する。テスト成功後、対象プロジェクトだけcommit/pushし、push成功後だけDiscord通知する。
