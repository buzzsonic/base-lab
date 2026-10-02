# NEXT_TASK

1. discovery/observe実装のPRとActionsを確認し、data branchへの実保存・再実行・API失敗時の挙動を検証する。定期実行の開始はmain反映後。
2. JST 4時間帯のpublic Trades coverageを蓄積し、固定100候補を日次observeする。取得失敗を観察日数として数えない。
3. 新しいdiscoveryから100件の層化再PoCを行い、旧cap63%・小型アルト2%と比較する。10,000件retention制約を2,000件capと区別して報告する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. 7日経過・7日分完全取得のpromotionを実データで検証し、sample品質ゲートとsnapshot/weekly永続化を統合する。既存snapshot/weeklyは骨組みのまま。
6. cap率と小型アルトcoverageの再ゲート通過後にのみ1,000-wallet拡大を検討する。現在はHOLD。
