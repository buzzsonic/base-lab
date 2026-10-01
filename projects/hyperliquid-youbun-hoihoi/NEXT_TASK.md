# NEXT_TASK

1. `userFillsByTime`増分checkpointへ移行し、2,000件cap率を63%からさらに下げる。
2. candidate履歴mergeと7日後promotionを実装する。
3. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
4. snapshot/weekly処理とdiscovery artifactをdata branchへ安全に永続化する統合テストを追加する。
5. public Trades collectorを4つのJST時間帯で実行し、日次coverageと欠測を検証する。
6. cap率と小型アルトcoverageの再ゲート通過後にのみ1,000-wallet runを行う。
