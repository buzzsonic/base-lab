# Pilot 100 reconstruction root-cause audit

## 結論

初回差異の主因は2つ確認できた。

1. `userFillsByTime` / `userFunding`の2,000件 / 500件ページ境界で、旧実装が末尾timestampへ`+1ms`していたため、同一millisecondの残りrecordsを落としていた。
2. 通常fillsと別endpointのTWAP sliceを同一timestamp内で単純連結していたため、観測済み`startPosition`鎖の順序が壊れていた。

修正ページングでは境界timestampを重ね、tidまたはrow hashでdeduplicateする。同一timestampのfillは観測済み`startPosition → afterPosition`鎖でinterleaveする。欠落値の推定はしていない。

P077の実証ではfillsが12,079→12,329（+250）、continuity errorが6→0になった。Fundingも全100口座を再取得し、505,011→535,462（+30,451）となった。

## 再取得不能による停止

修正版再取得時点でrolling retentionが進み、36口座は元の固定期間先頭を再取得できなかった。完全比較可能64口座のうち、TWAP retention gap 5口座、復元不能fill gap 2口座、perp fill 0や完結episode 0を除くと、全品質条件を満たすのは44/100口座だった。

- eligible wallets: 44
- excluded wallets: 56
- eligible completed episodes: 22,973
- eligible quantity mismatch: 0
- eligible continuity error: 0

56%除外はsampling biasが大きいため、OHLCV・behavior label・500口座拡大へ進まない。固定100口座を差し替えず、forward collectorでfills/TWAP/Fundingをappend-only保存してから新しい観測期間を開始する設計変更が必要。

個別wallet addressは本reviewへ保存せず、固定aliasだけを使用した。raw v1/v2はGit非管理で保持する。
