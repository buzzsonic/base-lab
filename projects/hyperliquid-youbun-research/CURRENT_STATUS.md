# CURRENT_STATUS

更新日: 2026-10-02 JST

## Current Phase

PoCデータ品質検証。episode再構成・会計照合・5分市場系列coverage棚卸しを完了し、限定的なpast-only価格・出来高特徴量の実装判断段階。

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
- eligible 10口座・完結61episodeのclosedPnl、fee、Funding、net PnL会計照合61/61 PASS
- Fundingは44episodeで非zero、合計-1,004.713607 USDC
- builderFeeは9episodeで非zero、合計565.678405 USDC。全件fee内包で二重計上0
- eligible口座のTWAP追加0件、TWAP 2,000件上限口座の除外をtestとレポートで固定
- eligible 10口座・完結61episodeのentry前60分／entry後60分の市場series coverageを全件確定
- entryを含む未確定5分足を除外し、直前12本だけをentry特徴量窓にするpast-only契約をtest化
- FEATURE_READY 0、PARTIAL 24、NOT_READY 37。OHLCV/volume完備24、Fundingは60/61でentry以前2時間内に観測
- historical mark/OIは61件すべてNULL/unavailableとし、推定・0埋めを行わなかった

## Latest Work

- TWAP上限2,000件に達し連続性エラー15件が残る1口座を分析対象外とした。
- perp fill 0件の1口座を対象外とした。
- 層別レビューは10口座をすべて含み、勝敗10/10、Long/Short 10/10、反転境界2/2を確認した。
- 非zero builderFeeを含む3サンプルで、builderFeeをfeeへ再加算しないことを確認した。
- 全61episodeでもbuilderFeeを別加算せず、`closedPnl - fee + Funding`がprocessed net PnLと一致した。
- 旧`account_quality.csv`はperp fill 0口座のstored eligible flagが1件だけ古い。今回と現行コードは再計算条件で正しく除外しており、次回PoC再生成時にキャッシュを更新する。
- 養分行動分類はまだ開始していない。
- 公式candleの直近5,000本制限により、37episodeはentry前60分の5分足が0/12でNOT_READY。
- PARTIAL 24episodeはpast-onlyのprice return／volume特徴量だけ許容する。mark/OI/Funding依存特徴量へ暗黙利用しない。

## Tests

- `python3 -m unittest discover -s tests -v`
- 19 tests passed（従来14件＋市場coverage 5件）
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

会計照合は61/61 PASS、二重計上0、重大差異0。

成果物: `reviews/accounting-quality-2026-10-02/`。

## Next

PARTIAL 24episodeに限定し、past-onlyのprice return／volume特徴量を別成果物として付与する。mark/OI依存特徴量と欠測Funding 1件はNULLのままにし、FOMO、Late Long/Short、ナンピン、Revenge、Trapped、Crowding分類はまだ開始しない。
