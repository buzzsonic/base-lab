# Pilot 100 quality stop report

## 判定

PHASE 1はPASS、PHASE 2のwallet endpoint収集は100/100成功した。PHASE 3の初回再構成で重大差異を検出したため停止した。500口座拡大はFAILではなく、原因修正までHOLDとする。

## 主要数値

- sampling: 100 wallet、duplicate 0、exploratory 60 / validation 20 / held_out 20
- source universe: Hoihoi public Trades実時間598 wallet、固定commit `4fea9437aac3036f7fb64abc74ae37e23a7e906a`
- raw fills: 674,339
- TWAP slice fills追加: 8,452
- Funding rows: 505,011
- perp fills after merge: 680,842
- reconstructed episodes: 46,182
- completed uncensored episodes: 44,125
- quantity mismatches: 107 episodes / 33 wallets
- continuity errors: 3,790 / 47 wallets
- endpoint collection failures: 0
- pagination safety cap hits: fills 0 / Funding 0 / TWAP 0

## 停止理由

`quantity mismatch = 0` と `continuity errorは説明可能` のGateを満たさない。差異を除外や補完で隠さず、fill/TWAP merge、同時刻順序、APIページ境界、期間開始前positionの順にraw traceで原因分類する。原因解消前はOHLCV収集、label適用、結果比較、500口座拡大を行わない。

rawとcheckpointはGit非管理の`data_pilot100/`に保存した。walletを含む個別品質表は公開レポートへ複製していない。

## 2026-10-03追補

原因監査でページ境界`+1ms`とTWAP同時刻順序を特定した。修正版でeligible 44口座はquantity mismatch 0・continuity error 0になったが、rolling retention等で56口座を除外する必要がありsampling biasが大きいため、pilotは引き続き停止。詳細は`reviews/pilot-100-reconstruction-audit-2026-10-03/`。
