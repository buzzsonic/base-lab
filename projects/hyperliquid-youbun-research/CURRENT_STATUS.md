# CURRENT_STATUS

更新日: 2026-10-02 JST

## Current Phase

PoCデータ品質検証。outcome-blindラベル品質レビューと100〜500口座への拡大設計まで完了し、100口座pilotの収集・再構成準備段階。

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
- PARTIAL 24episodeへentry以前の確定12本だけからprice/volume/local structure特徴量を付与
- BTC相対特徴量は24/24、Funding rateは23/24。mark/OIは24/24でNULLを維持
- 24episode ID一意、数値特徴量有限、range position範囲内、再実行CSV同一を確認
- FOMO / Late / Averaging Down / Profit Pyramiding / Revenge Candidateのv1定義・閾値・tri-state schemaを事前登録
- 24episode dry-runはFOMO 1、Late 2、Averaging Down 4、Profit Pyramiding 8、Revenge Candidate 4。Revenge 6件は前episode不足でUNAVAILABLE
- dry-run成果物にPnL・勝敗・MFE/MAE・post-entry結果を含めず、再実行同一を確認
- PHASE 3としてwallet・coin・side・重複パターン別のoutcome-free分布サマリを作成
- TRUEを含む14episode全件＋層別all-FALSE 7episodeをoutcome-blind再照合し21/21 PASS
- 100口座pilot→500口座拡大、探索60%・validation 20%・held-out 20%、目標2,000episodeの設計を固定

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
- entry足、exit時刻、PnL、MFE/MAE、post-entry candleは特徴量計算interfaceから物理的に除外した。
- 24件は特徴量パイプラインのPoCとして使用可能だが、行動別成績や「逆指標」の統計結論には少なすぎる。
- label config v1.0.0はdry-run後に固定。閾値変更はv1上書きではなくv2を作る。
- FOMO/Late重複はschema上許可しsynthetic test済みだが、今回の24件では重複0。
- 個別addのpre-add平均・add価格・stable order traceがdry-run成果物に未保存。100口座pilot前の監査証跡追加が必要。

## Tests

- `python3 -m unittest discover -s tests -v`
- 38 tests passed（従来37件＋outcome-blind選定1件）
- 専用Secret `DISCORD_WEBHOOK_URL_YOUBUNKUN` を使用。
- Discord 403は解消済み。
- 最終成功通知run: `36956495550`。

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

100口座pilot前にoutcome-free add evidence tableを実装し、その後層化候補100口座を固定してraw fills/TWAP/Funding/5分足の収集計画を実行する。再構成・会計誤差0を維持できない場合は500口座へ進まない。
