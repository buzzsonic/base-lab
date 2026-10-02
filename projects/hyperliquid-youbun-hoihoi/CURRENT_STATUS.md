# CURRENT_STATUS

更新: 2026-10-02 JST（PR #14・#20統合、初回実収集と100候補の初回観察成功）

| item | state |
|---|---|
| active wallets / research sample | 0 / 0（7日観察前の即時昇格は禁止） |
| discovery pool / selected candidates | 200 / 100（未選抜100件を保持） |
| selected status | OBSERVING 44、EXCLUDED 41、INACTIVE 15 |
| flags in selected 100 | BOT 38、MM 10、arbitrage 1、farm 1（重複し得る） |
| historical fills | 79/100で30日区間を完全取得、21/100はAPIの直近10,000件保持制約で不完全 |
| small-alt-centric | 2/100（層化再PoCの偏りは未解決） |
| latest snapshot / weekly | NOT RUN / NOT RUN（本体の永続化は未実装） |
| last completed observation | [36991127825](https://github.com/buzzsonic/base-lab/actions/runs/36991127825) success（同日再観察） |
| current blocker | 7日間・7 JST日分の完全取得はまだ満たさない。1,000-wallet拡大はHOLD |

## Issue #8 の比較基準

| 指標 | 旧100件 | 層化後100件 |
|---|---:|---:|
| userFills 2,000件cap | 84% | 63% |
| BOT疑い | 52% | 38% |
| MM疑い | 17% | 9% |
| inactive | 14% | 15% |
| 高頻度 / 中頻度 / 低頻度 | 67% / 16% / 17% | 48% / 30% / 22% |
| 重複 | 0% | 0% |

層化後の規模帯は小口30・中口52・大口3・不明15。銘柄傾向はBTC/ETH中心38・アルト中心45・小型アルト中心2・不明15。旧2,000件cap率63%と今回の10,000件retentionによる不完全21%は異なる指標であり、直接の改善率として扱わない。

## 実運用の検証

- [PR #14](https://github.com/buzzsonic/base-lab/pull/14)でpublic Trades収集、userFillsByTime分割・checkpoint、7日観察条件と日次workflowを統合。24テスト成功。
- [収集run 36956559938](https://github.com/buzzsonic/base-lab/actions/runs/36956559938)はsuccess。原JSONLで再照合すると開始後の実時間約定2,952件、wallet598件、22/22銘柄、小型アルト12/12銘柄。再接続・解析エラー0。次の手動収集[36957019109](https://github.com/buzzsonic/base-lab/actions/runs/36957019109)もsuccess。
- [観察run 36956559977](https://github.com/buzzsonic/base-lab/actions/runs/36956559977)はsuccess。100候補のcheckpointとregistryをdata branchへ保存。79件の30日区間は完全、21件はAPIの直近10,000件retentionで不完全。早期昇格0件。
- 初回観察がpoolを100件へ縮めたため、data branchのpoolを200件へ復元（commit `4f904d7`）。[PR #20](https://github.com/buzzsonic/base-lab/pull/20)で次回以降の未選抜行保持、Parquetの列union、収集成功後の観察起動を修正。25テスト成功。
- 修正後の[push収集run 36990610067](https://github.com/buzzsonic/base-lab/actions/runs/36990610067)と[定刻収集run 36990861363](https://github.com/buzzsonic/base-lab/actions/runs/36990861363)はsuccess。[連動観察run 36991127825](https://github.com/buzzsonic/base-lab/actions/runs/36991127825)もsuccess。再保存後もpool 200件（選抜100件）、registry 100件、sample 0件、first_seen 100/100一致。成功観察日は79件が1日、21件が0日で同日二重加算なし。定刻収集に由来する[別の観察run 36991640533](https://github.com/buzzsonic/base-lab/actions/runs/36991640533)は、workflowのpush限定条件によってskipped。小型アルト比率とheuristicの目視検証、snapshot/weekly永続化を次工程とする。詳細は `QUALITY_REPORT_RUNTIME_2026_10_02.md`。
