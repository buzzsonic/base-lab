# NEXT_TASK

1. 専用public Trades discovery collectorを実装し、複数JST時間帯・主要/アルト/小型アルトのcoverageを日次で蓄積する。
2. `userFillsByTime`増分checkpointへ移行し、2,000件cap率を63%からさらに下げる。
3. candidate履歴mergeと7日後promotionを実装する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. snapshot/weekly処理をdata branchへ安全に永続化する統合テストを追加する。
6. cap率と小型アルトcoverageの再ゲート通過後にのみ1,000-wallet runを行う。
