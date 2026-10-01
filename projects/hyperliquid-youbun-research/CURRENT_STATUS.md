# CURRENT_STATUS

更新日: 2026-10-01 JST

## Current Phase

PoCデータ品質検証。行動分類前のTWAP/Funding/fee帰属とepisode目視検証段階。

## Completed

- 12口座・30日の読み取り専用PoC
- raw fills 7,783、perp fills 5,383、position episodes 84
- 完結・期間開始前持ち越しなし66、数量不一致0、清算観測0
- zero-to-zero、部分決済、追加、反転の再構成
- TWAP/Funding取得とepisode時間窓へのFunding帰属
- startPosition連続性ゲートを追加
- 過去分析とリアルタイム観測のdata contractを分離

## Latest Work

- TWAP上限2,000件に達し連続性エラー15件が残る1口座を分析対象外とした。
- perp fill 0件の1口座を対象外とした。
- 次の目視検証母集団は10口座・完結61episode。
- ChatGPT/Codex/GitHub/Discord共有運用の状態ファイルと通知スクリプトを追加。

## Tests

- `python3 -m unittest discover -s tests -v`
- 7 tests passed（再構成5件、Discord通知文2件）
- Discord通知スクリプトはdry-run成功。Webhook値は未設定・未表示・未保存。
- GitHub Actions用の手動完了通知workflowを追加。養分くん専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN`の存在を値非表示で確認。
- PR #2をmainへmergeし、通知workflow run `36871273127`を実行。Secretはworkflowへ渡ったがDiscordがHTTPErrorを返し、実送信は失敗。成功通知は送っていない。
- PR #4で専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN`へ切替済み。run `36873062707`でもSecretは渡ったがDiscordがHTTPErrorを返し、通知は未送信。
- PR #5で安全なHTTP診断を追加。run `36873349619`で `HTTP 403 Forbidden` を確認し、Secret名・未設定ではなくDiscord側のリクエスト拒否と特定。

## Known Limitations

- 現在の建玉・レバレッジ設定・清算価格は直接取得可能だが、任意の過去cross-margin状態と清算直前equityは正確な復元が困難。
- candleは直近5,000本、5分足で約17日。
- leaderboardには高頻度whale、spot中心、期間内無活動口座が混ざる。
- 清算0件は存在しないという意味ではなく、今回の標本では未観測。
- REST APIにはweight-based rate limitがある。
- WebSocketではfills、funding、liquidation user event、L2、BBO、trades、account stateを今後取得可能。

## Blockers

- 専用Secret名への切替は完了。Discordが `HTTP 403 Forbidden` を返すため、明示的なUser-Agentを付けた再送確認が必要。
- ローカル`YOUBUN_DISCORD_WEBHOOK_URL`は未設定。
- TWAP endpoint上限到達口座は完全な履歴を取得できず、行動分析対象外。

## Next

完結61episodeから層別目視サンプルを作り、fill列・追加・部分決済・反転・PnL・fee・Fundingを原データと照合する。その後、5分市場系列coverageを定量化する。
