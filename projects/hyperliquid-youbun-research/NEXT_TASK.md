# NEXT_TASK

作業開始時は `PROJECT_CONTEXT.md`、`CURRENT_STATUS.md`、本ファイル、`DECISIONS.md` を先に読む。

# 運用方針

原則2〜3工程を連続実行する。
各Gate PASS後はユーザー確認を待たず次工程へ進む。

停止条件:
- raw evidenceで説明できないquantity mismatch
- accounting mismatch
- future leakage
- sampling leakage
- データ破損
- API制約で設計変更が必要
- GitHub競合
- 研究結果を大きく左右する未決仕様

軽微な命名・実装詳細は合理的に決めて続行する。

養分ホイホイ側は読み取り専用。変更しない。

---

# 現在地

100口座pilot:

- sampling固定: PASS
- 100/100 wallet endpoint収集成功
- raw fills: 674,339
- TWAP追加: 8,452
- Funding: 505,011
- merge後perp fills: 680,842
- reconstructed episodes: 46,182
- completed uncensored: 44,125
- quantity mismatch: 107 episodes / 33 wallets
- continuity error: 3,790 / 47 wallets

PHASE 3 Gate FAIL。
500口座拡大はHOLD。

---

# STOPPED GATE: API retentionに対応するforward collector設計

2026-10-03原因監査結果:
- 旧ページングの`max(timestamp)+1ms`が同一timestamp recordsを欠落させた
- 修正は境界timestamp overlap＋tid/row hash dedup
- 通常fillとTWAP sliceは観測済みstartPosition鎖で同一timestamp順序を復元
- Funding 100口座再取得で+30,451 rows
- rolling retentionにより36口座は旧固定期間と完全比較不能
- 最終eligible 44/100、excluded 56/100
- eligible完結22,973episode、quantity mismatch 0、continuity error 0

停止理由:
- 56%技術除外はsampling biasが大きい
- 過去30日を後追い取得する設計では高頻度口座のraw完全性を保証できない
- `API制約で設計変更が必要`に該当

次に設計すること:
1. 固定100 walletを変更せず、fills / TWAP / Fundingをappend-only保存するforward collector
2. 境界timestamp overlap、dedup key、raw server order、source endpoint、ingested_atを保存
3. wallet×endpoint checkpoint、gap、retry、retention/cap flagを永続化
4. collector開始時刻を新しいanalysis periodの固定startとし、それ以前を推定しない
5. WebSocketと定期REST overlap取得の役割分担、実行間隔、保存先、data branch運用を決定
6. 7日以上のshadow collectionでcontinuity error 0を確認してからpilotを再開

設計変更が確定するまでOHLCV・label・500口座拡大は禁止。

---

# ARCHIVE: main側の初期raw trace監査計画

以下の監査計画は2026-10-03に実施済み。結果は
`reviews/pilot-100-reconstruction-audit-2026-10-03/`を正本とする。

107件を全件raw evidenceへ戻して分類する。

最低限の分類軸:
- wallet
- coin
- episode_id
- timestamp
- reversal有無
- partial close有無
- add有無
- TWAP追加有無
- 同一timestamp fill有無
- API page boundary近傍
- duplicate tid/hash有無
- left-censored可能性
- source endpoint
- fill ordering key

成果物:
`reviews/pilot-100-reconstruction-audit-v1/`

最低限:
- README.md
- quantity_mismatch_audit.csv
- representative_raw_traces/
- root_cause_summary.csv

各mismatchに必ず:
- observed mismatch
- expected quantity
- reconstructed quantity
- raw trace
- root cause category
- fixability
- fix applied
- post-fix result

を持たせる。

禁止:
- fill推定
- forward fill
- 数量合わせの補正
- mismatch episodeの黙示除外

---

# PHASE 2: continuity error 3,790件の原因分解

全件を最低限以下へ分類する。

- left censoring / pre-period open position
- API page boundary
- same timestamp ordering
- duplicated fill
- missing fill evidence
- TWAP merge ordering
- reversal reconstruction
- endpoint retention/window limit
- genuine unexplained

wallet・coin別件数も保存。

重要:
continuity error自体を0にすることが目的ではない。
「説明可能なcensoring/取得制約」と「再構成バグ」を分離する。

成果物:
- continuity_error_audit.csv
- category_summary.csv
- unexplained_cases.csv

---

# PHASE 3: ordering / merge contract修正と再構成再試験

PHASE 1/2で原因が証明されたものだけ修正する。

重点確認:
- userFillsByTimeのpage merge順
- timestamp同値時のstable secondary key
- tid / hash / source sequence
- TWAP fillと通常fillのmerge
- reversal時のclose/open split
- partial close後のposition state
- startPositionとの連続性
- API page overlap重複排除

必要ならcanonical fill ordering contractを明文化し、
`DECISIONS.md` とtestへ固定する。

test追加:
- same-ms multiple fills
- same-ms reversal
- TWAP + normal fill same window
- page overlap
- duplicate tid
- partial close + add
- pre-period open position
- left-censored episode exclusion

## 再構成Gate

修正後、100口座全件を再実行。

PASS条件:
- quantity mismatch = 0
-重大 accounting mismatch = 0
- unexplained continuity error = 0
- explained continuity/censoringはcategory付きで保存
- sampling manifest不変
- future leakage test PASS
- 全tests PASS
- raw→episode再実行で再現可能

---

# PHASE 4: Gate PASS後のみpilot再開

再構成GateがPASSした場合のみ続行。

次に:
1. 未実行OHLCV / BTC reference series収集
2. market coverage再計算
3. past-only feature生成
4. label v1 availability確認
5. pilot-100品質サマリ更新

成果物:
`analysis/pilot-100-v1/`

500口座Gate:
- quantity mismatch 0
- unexplained continuity 0
- accounting mismatch 0
- API負荷許容
- cap/retention影響把握済み
- sampling biasなし
- test PASS

PASSならNEXT_TASKを500口座拡大へ自動更新。
FAILなら500はHOLDし、原因と修正案を記載。

---

# 作業終了時

必ず:
- CURRENT_STATUS.md更新
- NEXT_TASK.md更新
- 必要ならDECISIONS.md更新
- 全test実行
- 養分くん対象ファイルだけcommit/push
- push成功後のみ養分くん専用Discord通知

完了報告:
1. mismatch 107件の原因内訳
2. continuity 3,790件の原因内訳
3. 修正内容
4. 再構成後の数値
5. Gate PASS/FAIL
6. 500口座へ進めるか
