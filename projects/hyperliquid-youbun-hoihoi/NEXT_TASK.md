# NEXT_TASK

1. PR #14はmain統合済み、discovery実取得・data保存は成功。observation run `36956559977` の完了を確認し、100候補のcheckpoint・registry・観察履歴の実保存と再実行を検証する。
2. JST 4時間帯のpublic Trades coverageを蓄積し、固定100候補を日次observeする。取得失敗を観察日数として数えない。
3. 新しいdiscoveryから100件の層化再PoCを行い、旧cap63%・小型アルト2%と比較する。10,000件retention制約を2,000件capと区別して報告する。
4. 100件から20件を層別目視し、BOT/MM/farm/裁定heuristicの誤検知を確認する。
5. 7日経過・7日分完全取得のpromotionを実データで検証し、sample品質ゲートとsnapshot/weekly永続化を統合する。既存snapshot/weeklyは骨組みのまま。
6. cap率と小型アルトcoverageの再ゲート通過後にのみ1,000-wallet拡大を検討する。現在はHOLD。
