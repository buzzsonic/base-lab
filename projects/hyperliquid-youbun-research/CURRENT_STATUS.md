# CURRENT_STATUS

更新日: 2026-10-02 JST

## Current Phase

PoCデータ品質検証。episode層別目視ゲートを通過し、TWAP/Funding/builder fee会計照合の最終確認段階。

## Completed

- 12口座・30日の読み取り専用PoC
- raw fills 7,783、perp fills 5,383、position episodes 84
- 完結・期間開始前持ち越しなし66、数量不一致0、清算観測0
- zero-to-zero、部分決済、追加、反転の再構成
- TWAP/Funding取得とepisode時間窓へのFunding帰属
- startPosition連続性ゲートを追加
- 過去分析とリアルタイム観測のdata contractを分離
- ChatGPT/Codex/GitHub/Discord共有運用を構築
- 養分くん専用Discord通知を実送信確認済み
- eligible 10口座・完結61episodeの境界・数量・価格・PnL・fee・Fundingを独立再計算し、61/61一致
- 勝敗、Long/Short、追加、部分決済、反転、保有時間、fill数を跨ぐ20episodeを匿名化レビューし、20/20 PASS

## Latest Work

- TWAP上限2,000件に達し連続性エラー15件が残る1口座を分析対象外とした。
- perp fill 0件の1口座を対象外とした。
- 層別レビューは10口座をすべて含み、勝敗10/10、Long/Short 10/10、反転境界2/2を確認した。
- 非zero builderFeeを含む3サンプルで、builderFeeをfeeへ再加算しないことを確認した。
- 養分行動分類はまだ開始していない。

## Tests

- `python3 -m unittest discover -s tests -v`
- 10 tests passed（再構成5件、Discord通知文2件、episodeレビュー3件）
- 専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN` を使用。
- Discord 403は解消済み。
- 最終成功通知run: `36873755127`。

## Known Limitations

- 現在の建玉・レバレッジ設定・清算価格は直接取得可能だが、任意の過去cross-margin状態と清算直前equityは正確な復元が困難。
- candleは直近5,000本、5分足で約17日。
- leaderboardには高頻度whale、spot中心、期間内無活動口座が混ざる。
- 清算0件は存在しないという意味ではなく、今回の標本では未観測。
- REST APIにはweight-based rate limitがある。
- TWAP endpoint上限到達口座は完全な履歴を取得できず、行動分析対象外。

## Passed Gate

完結61episodeの全件自動照合と、20episodeの層別目視レビューで重大差異0。

成果物: `reviews/episode-quality-2026-10-02/README.md` と `episode_review.csv`。

## Next

TWAP/Funding/builder fee会計照合を最終確認する。今回のeligible口座には非zero TWAP追加がないため、TWAP上限口座を除外する設計とfixtureを明示し、FundingとbuilderFeeは実サンプルのcoverageを集計する。

その後に5分市場系列coverageを定量化する。FOMO、Late Long/Short、ナンピン、Revenge、Trapped、Crowding分類はまだ開始しない。
