# 養分ホイホイ 実行検証 2026-10-02

## 統合と収集

- [PR #14](https://github.com/buzzsonic/base-lab/pull/14)をmain@7863416へ統合。24件のunittest、workflow YAML parse、diff check成功。
- [discovery run 36956559938](https://github.com/buzzsonic/base-lab/actions/runs/36956559938) success。収集時間は2026-10-02 11:38:43–11:43:43 JST。
- 主要2・アルト8・小型アルト12、計22銘柄で約定を観測。snapshotを含む取引3,612件・ユニークwallet673件。再接続0、解析エラー0。
- 原JSONLをtime/coin/tidで重複排除し、trade.time >= started_atだけに絞った再照合では、実時間取引2,952件、wallet598件、22銘柄、小型アルト12/12銘柄。raw・市場snapshot・coverageをdata branchへ保存。
- [二度目のdiscovery run 36957019109](https://github.com/buzzsonic/base-lab/actions/runs/36957019109)もsuccess。JST 12–17時帯の収集を保存。

## 初回100候補の観察

- [observation run 36956559977](https://github.com/buzzsonic/base-lab/actions/runs/36956559977) success。100 wallet checkpoint・registryをdata branchへ保存。poolの選抜100件とfirst_seenは100/100で一致し、早期promotionは0件。
- 79/100で30日間のfill履歴を完全に取得。21/100はAPIの直近10,000件保持制限により過去区間を完全には復元できない。913 API呼出し、2,000件に達した応答410回、重複排除後の保存約定483,812件。
- 初回selected statusはOBSERVING 46、EXCLUDED 39、INACTIVE 15、ACTIVE 0。BOT疑い38、MM疑い10、arbitrage疑い1、farm疑い1。小型アルト中心は2/100のまま。
- Issue #8の旧「2,000件cap 63/100」と今回の「10,000件retentionによる不完全21/100」は測定対象が異なるため、63%→21%という同一指標の改善とは表現しない。

## pool保持の修正と残課題

- 初回観察はpoolを200件から100件に上書きした。data branchで未選抜100件を保持して200件へ復元（`4f904d7`、registryは100件、sampleは0件）。
- [PR #20](https://github.com/buzzsonic/base-lab/pull/20)をmain@4ae4debへ統合。既存poolの未選抜行とfirst_seenを保持し、新旧行の列をunionしてParquet保存。収集成功後に観察を連動させる。25テスト、workflow YAML parse、diff check成功。
- 修正後の[push収集run 36990610067](https://github.com/buzzsonic/base-lab/actions/runs/36990610067)、[定刻収集run 36990861363](https://github.com/buzzsonic/base-lab/actions/runs/36990861363)、[連動観察run 36991127825](https://github.com/buzzsonic/base-lab/actions/runs/36991127825)はsuccess。再観察後のpoolは200件（poc_selected 100件）、registry 100件、sample 0件。first_seenは100件共通で維持。成功観察日数は79件が1日・21件が0日で同日二重加算なし。statusはOBSERVING 44、EXCLUDED 41、INACTIVE 15へ更新。[別の観察run 36991640533](https://github.com/buzzsonic/base-lab/actions/runs/36991640533)はschedule由来のworkflow_runがpush限定条件に合わずskipped。
- 7日観察条件、小型アルト2%、heuristicの目視検証、snapshot/weekly永続化は未達。1,000-wallet拡大はHOLD。
