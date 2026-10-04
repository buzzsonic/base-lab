# CURRENT_STATUS

更新: 2026-10-03 JST（翌日観察、4時間帯coverage、隔離200→100再PoC成功）

## 2026-10-04 BTC研究sample契約

- 養分ホイホイの役割をBTC event-studyの上流へ変更し、`contracts/btc-research-sample-v0.1/`に選抜config、handoff JSON Schema、exampleを追加した。
- `hoihoi.handoff.validate_handoff`は品質Gate、重複、最低BTC activity、profile根拠、outcome field混入をfail-closedで検査する。
- 36テスト成功。実sampleは未生成で、現行・shadow registryも変更していない。次は既存200 walletへのoutcome-blind dry-run。

## 2026-10-04 BTC研究sample dry-run

- data `91c89b4`のcurrent 100件・shadow 100件へv0.1をoutcome-blind適用。39テスト成功、registry/sample変更なし。
- BTC activity 3条件通過はcurrent 32・shadow 25、再構成品質clearはcurrent 51・shadow 59。観察日・TWAP・市場window以外の暫定Gate通過はcurrent 0・shadow 2。
- 全200件でTWAP evidenceなし・7日未達。checkpointのhash tie-sortにより同一ms順序不明がcurrent 49・shadow 40。最終handoff適格は0でHOLD。
- 次は既存checkpointを修復せず、server order保持fills・別TWAP raw・past-only BTC market windowの新forward contractを作る。

| item | state |
|---|---|
| active wallets / research sample | 0 / 0（7日観察前の即時昇格は禁止） |
| discovery pool / selected candidates | 200 / 100（未選抜100件を保持） |
| selected status | OBSERVING 45、EXCLUDED 40、INACTIVE 15 |
| flags in selected 100 | BOT 39、MM 12、arbitrage 1、farm 1（重複し得る） |
| historical fills | 79/100で30日区間を完全取得、21/100はAPIの直近10,000件保持制約で不完全 |
| small-alt-centric | 現行0/100、新隔離cohort 9/100 |
| latest snapshot / weekly | [37116871931](https://github.com/buzzsonic/base-lab/actions/runs/37116871931) success / [37172824334](https://github.com/buzzsonic/base-lab/actions/runs/37172824334) success |
| last completed observation | [37116402104](https://github.com/buzzsonic/base-lab/actions/runs/37116402104) success（79件が2成功JST日、21件が0日） |
| current blocker | 7日間・7 JST日分の完全取得はまだ満たさない。1,000-wallet拡大はHOLD |

## 2026-10-03 隔離再PoC

- [再PoC run 37116104107](https://github.com/buzzsonic/base-lab/actions/runs/37116104107)はsuccess。59分23秒でfresh 200件を評価し、100件を層化選抜した。artifactのみで、現行registryは変更していない。
- 新100件は履歴完全98、不完全2、BOT疑い29、MM疑い4、farm疑い6、small-alt中心9。現行100件との重複は42件。
- 新100件の成功観察日は完全取得98件が1日、欠損2件が0日。7日・7 JST日分のgateは未達。
- 20件の層別レビューではheuristic閾値との不一致0件。ただしMM/farmは戦略確定ではないため、疑いラベルと保守的除外を維持する。
- 詳細は `QUALITY_REPORT_STRATIFIED_POC_2026_10_03.md`。

## 2026-10-03 shadow cohort 初回観察

- [PR #28](https://github.com/buzzsonic/base-lab/pull/28)をmain@`71bce6e`へ統合。`stratified-20261003`を現行とは別namespaceで毎日03:20 JSTに観察する。
- data branch `3b4c0ab`へseed後、[run 37120774019](https://github.com/buzzsonic/base-lab/actions/runs/37120774019)がsuccess。保存commitは`bb4709f`。
- 変更パスはshadow配下のみ。`outputs/current/`のtree hashは実行前後とも`96e57802da37182ec82f0d5461cdbbf3c257d992`で一致。
- shadowはregistry 100、pool 200、checkpoint 100、sample 0。成功観察日は98件が1日・2件が0日のまま。
- live再取得では履歴完全97、不完全3。1 walletが完全→不完全へ変化し、成功日は加算されなかった。BOT 29、MM 4、farm 6は維持、small-altは10。

## 2026-10-04 定刻観察

- 現行[run 37147375366](https://github.com/buzzsonic/base-lab/actions/runs/37147375366)とshadow[run 37154398261](https://github.com/buzzsonic/base-lab/actions/runs/37154398261)はsuccess。
- 現行: 成功観察日79件が3日、21件が0日。完全79、不完全21、OBSERVING 46、EXCLUDED 39、INACTIVE 15、sample 0。
- shadow: 成功観察日97件が2日、1件が1日、2件が0日。完全97、不完全3、OBSERVING 54、EXCLUDED 30、INACTIVE 16、sample 0。
- shadowのBOT 27、MM 4、farm 6、small-alt 11。現行比で完全履歴+18、BOT -11、MM -8、small-alt +9だが、7日gate未達のため置換判断はHOLD。

## 2026-10-04 weekly品質Gate

- [PR #33](https://github.com/buzzsonic/base-lab/pull/33)で現行・shadowのreport-only比較を実装し、[PR #35](https://github.com/buzzsonic/base-lab/pull/35)で保存日付をJST固定、report専用queueへ分離した。32テスト成功。
- [run 37172824334](https://github.com/buzzsonic/base-lab/actions/runs/37172824334)はsuccess。data branch `1b7786e`が`outputs/reports/weekly/2026-10-04/cohort_comparison.json`だけを追加した。
- current / shadowとも構造GateはPASS。promotion Gateとreplacement Gateは7成功JST日未達のためHOLD。
- 初回runの`2026-10-03`はUTC日付で保存された既存記録として残し、以後はJST日付を正とする。自動置換・統合・通知・売買は行わない。

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

## 小型アルト候補の抽出修正

- [PR #21](https://github.com/buzzsonic/base-lab/pull/21)をmainへ統合。collectorのcoverage.jsonに記録した小型アルト銘柄を公開約定由来候補の独立した層とし、26テスト成功。
- 保存済み4収集runでの100イベント候補試算は、従来BTC/ETH 46・その他alt 54、修正後BTC/ETH 32・alt 36・small_alt 32。70 walletは共通、30 walletが入替。これは公開約定の候補枠の比較であり、30日履歴でのsmall_alt_core 2/100の改善はまだ未確認。
- JST 00–05時帯の定刻収集と、200→100再PoCでの実際の選抜・retention率を次に検証する。1,000-wallet拡大はHOLD。

- PR #21統合後の[収集run 37017140756](https://github.com/buzzsonic/base-lab/actions/runs/37017140756)はsuccess。22/22銘柄・小型アルト12/12銘柄、ユニークwallet 2,220件、収集エラー0。[連動観察run 37017796437](https://github.com/buzzsonic/base-lab/actions/runs/37017796437)もsuccess。pool 200、registry 100、sample 0、成功日数79件が1日・21件が0日を維持。
