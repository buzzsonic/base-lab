# PoC status — 2026-10-01 JST

## 実行範囲

- 公式leaderboardから、月間出来高10万〜1,000万USDC・account value 100USDC以上を抽出
- 月間ROIの下位・中央・上位から合計12口座を決定論的に選択
- 対象期間: 2026-09-01 00:09:05〜2026-10-01 00:09:05 JST（30日）
- 公式 `userFillsByTime`、`aggregateByTime=false`
- rawはspotを含め保存し、position episodeはperpだけを対象

## 品質結果

| 指標 | 結果 |
|---|---:|
| アカウント | 12 |
| raw fills | 7,783 |
| perp fills | 5,383 |
| position episodes | 84 |
| 完結・left-censorなし | 66 |
| 期間開始前からの持ち越し | 8 |
| 期間末未決済 | 8 |
| 完結episodeの数量不一致 | 0 |
| 清算観測 | 0 |

## TWAP / Funding追試

- 12口座のFunding履歴を取得し、銘柄とepisode観測時間窓で帰属した。純損益は`realized PnL - fee + Funding`とし、`builderFee`は`fee`へ再加算しない。
- 1口座でTWAP slice endpointが上限2,000件に到達し、統合後も`startPosition`連続性エラー15件が残った。この口座の5完結episodeは行動分析から除外する。
- 1口座は期間内perp fillが0件のため除外する。
- 現時点の行動分析候補は10口座・完結61episode。これは統計結論用ではなく、次の目視検証母集団である。
- 数量一致だけではTWAP欠落を見逃せるため、`continuity_errors == 0`、TWAP endpoint非上限、完結episodeありを追加ゲートにした。

## 観測された問題と修正

1. PnL絶対額の極端な上下だけで選ぶと、高頻度whaleと期間内無活動口座に偏った。月間volume帯とROI層別へ変更した。
2. flip fillの新方向数量を旧episodeのentryにも加える二重計上をテストで検出し、旧closeと新openへ分離した。
3. `@`銘柄（spot）はinventory・feeの意味がperpと異なるため、rawには保持しつつperp episodeから除外した。
4. API 429を観測したため、Retry-After、長いbackoff、口座間待機、raw cache、固定end timeによる再処理を追加した。
5. leaderboardの月間値と対象30日のfillsが一致しない口座がある。leaderboard窓更新時刻、別DEX/spot、履歴coverageを次段で照合する。

## 現時点で言えること

- zero-to-zero再構成の基本数量整合は、このPoCの完結perp episodeで通過した。
- 12口座中1口座は対象期間fillsが0、ほかにもspot比率が高い口座がある。leaderboardだけでは均質なperp母集団にならない。
- 清算、late long、trapped、crowding、forward returnの統計的結論はまだ出せない。

## 次のゲート

1. TWAP slice fills、Funding、builder feeをrawへ追加してPnL照合
2. 66完結episodeの目視サンプルを生成
3. 5分candle/mark/OI coverageをepisode時刻と照合
4. FOMO/Late/Nanpin/Revengeの時点情報だけを使うラベルを実装
5. 目視一致後に100口座へ拡張
