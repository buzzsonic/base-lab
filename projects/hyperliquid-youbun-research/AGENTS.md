# 養分くんプロジェクト運用ルール

## 開始時

1. `PROJECT_CONTEXT.md`
2. `CURRENT_STATUS.md`
3. `NEXT_TASK.md`
4. `DECISIONS.md`

を必ず読む。必要に応じて`research_plan.md`、`POC_STATUS.md`、`REALTIME_DATA_CONTRACT.md`も読む。

`git branch --show-current`、`git status --short`、`git remote -v`、remoteとの差分を確認する。未commit変更をreset・上書きしない。対象外プロジェクトを変更・commitしない。

## 研究・安全

- 公開・読み取り専用データのみ。秘密鍵、注文、署名、資金移動は禁止。
- 品質ゲート通過前にFOMO/Late/ナンピン/逆指標の結論へ進まない。
- 取得不能値を推測で埋めず、欠測とcoverageを保存する。
- 既存BOT、workflow、DB、Discord通知を壊さない。

## 終了時

1. 実装・調査を完了する。
2. 関連テストを実行し、失敗中は成功扱いしない。
3. `CURRENT_STATUS.md`を更新する。
4. `NEXT_TASK.md`を更新する。
5. 重要判断は`DECISIONS.md`へ追記する。
6. `git diff`で対象プロジェクト以外が含まれないことを確認する。
7. 対象プロジェクトだけcommitする。
8. GitHubへpushする。
9. push成功後だけDiscord完了通知を送る。push失敗時はSUCCESSを送らない。

Discord Webhookは`YOUBUN_DISCORD_WEBHOOK_URL`環境変数からのみ読む。URLや秘密情報をファイル、ログ、commit、通知本文へ含めない。

ローカルWebhookがない場合は、default branchへworkflow導入後、`Youbun Research Completion Notification`を`gh workflow run`で起動し、養分くん専用GitHub Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN`を利用する。workflowが未mergeなら実送信待ちを明記し、成功と偽らない。
