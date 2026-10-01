# Issue #8 サンプリング偏り修正PoC

実行日: 2026-10-01 JST

## 結論

200ウォレットのdiscovery poolを作り、損益を使わず7軸のmarginal strata不足を埋めるgreedy方式で100ウォレットを選抜した。旧PoC比で高頻度、BOT/MM疑い、`userFills` capが明確に低下したため、Issue #8の抽出品質改善は確認できた。ただしcap 63%と小型アルト中心2%は十分ではなく、1,000ウォレット拡大は継続保留とする。

## 変更点

- 公開Trades: 先着walletを廃止し、JST時間帯×BTC/ETH/alt×event出現頻度proxyでround-robin
- Leaderboard: volume×equityに順位帯（top 1%、top 10%、middle 40%、bottom 50%）を追加
- 最終選抜: 実測の頻度、median notional、銘柄傾向、活動時間帯、活動日数、順位帯、sourceの不足層を優先
- 小型アルト: 公式`dayNtlVlm < 10M USDC`を設定可能な流動性proxyとして使用
- 未選抜pool: `discovery_pool.parquet`へ保持

## Before / after

| metric | before | after | change |
|---|---:|---:|---:|
| capped fill histories | 84% | 63% | -21pt |
| BOT suspected | 52% | 38% | -14pt |
| MM suspected | 17% | 9% | -8pt |
| inactive | 14% | 15% | +1pt |
| high frequency | 67% | 48% | -19pt |
| medium frequency | 16% | 30% | +14pt |
| low frequency | 17% | 22% | +5pt |
| duplicates | 0% | 0% | 0pt |

## After構成

- Source: public Trades 37 / official leaderboard 63
- Size: small 30 / medium 52 / large 3 / unknown 15
- Symbols: BTC/ETH core 38 / alt core 45 / small-alt core 2 / unknown 15
- Activity time: JST 00-05=23 / 06-11=18 / 12-17=20 / 18-23=24 / unknown=15
- Active days: 1-3=27 / 4-10=28 / 11+=30 / none=15
- Leaderboard band: top 1%=12 / top 10%=17 / middle 40%=23 / bottom 50%=11 / non-leaderboard=37

## 品質上の制約

1. `userFills`は直近2,000件上限で、高頻度口座の正確な30日件数ではない。
2. public Trades captureは3つの既存観測窓で、全時間帯・全銘柄の完全母集団ではない。
3. 小型アルトは時価総額ではなく現在の24h notional volume proxy。sample作成時の市場snapshot固定が未実装。
4. 初回candidateは7日観察前なので`research_sample.parquet`は0行のまま。

## 判定

- 抽出品質改善: PASS
- 1,000-wallet拡大: HOLD
- 次ゲート: 専用public Trades collector、`userFillsByTime`増分化、20件層別目視
