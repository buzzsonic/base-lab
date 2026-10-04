# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分くん関連commit差分だけ確認する。
`CURRENT_STATUS.md` / `DECISIONS.md` / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

fixed-100 forward collector v1/v2はGate FAILで凍結済み。
次版v3は、GitHub Actions scheduleを正本にせず、VPS上のDocker + systemd timerを正本schedulerとして実装する。

### PHASE 0: v3 scheduler事前登録

以下を先に固定する。

- runtime: Ubuntu VPS + Docker
- scheduler: systemd timer
- requested cadence: 5分
- hard requirement: 実測20分以内に1回以上collectorが完走または明示的FAIL
- overlap: 20分を維持
- single-flight: 同時起動禁止。前run実行中なら次runは重複実行せず、skip理由を記録
- timeout: 1 runの上限を明示し、timeout時はcheckpointを進めない
- retry: endpoint単位で有限回。最終FAIL時はcheckpointを進めない
- state: `forward-data-v3/`へ完全分離
- v1/v2 raw/stateはread-only監査証跡として保持し、v3へ混ぜない
- sample: fixed 100 wallets / sample SHA不変
- notification: retention risk / endpoint failure / cap hit / timeout / checkpoint rollback / data push conflictは即Discord通知
- GitHub Actions: unit/integration test、手動canary、fallback診断のみ。定期取得の正本にはしない

### PHASE 1: VPS実行パッケージをrepoへ追加

Codexは以下を実装する。

1. collector用Dockerfile / compose設定
2. `.env.example`（秘密値は含めない）
3. systemd service unit
4. systemd timer unit
5. single-flight lock
6. timeout / exit code / structured log
7. health/status確認コマンド
8. VPS初期セットアップ手順
9. restart後もtimerが自動復帰することの確認手順
10. data branch push競合時のfail-safe

成果物例:
- `deploy/vps/Dockerfile`
- `deploy/vps/docker-compose.yml`
- `deploy/vps/youbun-collector.service`
- `deploy/vps/youbun-collector.timer`
- `deploy/vps/README.md`

既存collectorロジックは可能な限り再利用し、scheduler差替えだけで済ませる。

### PHASE 2: local/CI dry-run

VPSへ入れる前にrepo上で以下を検証する。

- service commandが既存collectorを正しく呼ぶ
- lockで二重起動を防げる
- timeout時checkpoint非更新
- endpoint failure時checkpoint非更新
- data branch conflict時fail
- success時のみcheckpoint前進
- structured logにrun id / started_at / finished_at / duration / wallet count / endpoint count / failure / cap / retention riskを残す
- tests PASS

PHASE 2 PASS後のみVPS canaryへ進む。

### PHASE 3: VPS canary → fixed-100連続run

1. 1-wallet canary
2. fixed-100初回run
3. 少なくとも3回連続runを実測
4. 各runのstart間隔・duration・retention riskを記録
5. 20分以内条件を満たすことを確認

Gate:
- retention risk 0
- endpoint failure 0
- cap hit 0
- unresolved gap 0
- checkpoint rollback 0
- data branch conflict 0
- raw corruption 0
- sample SHA不変
- 連続runの実測間隔がすべて20分以内

PASSしたrun開始時刻をv3 analysis startとして固定し、その時点から7日Shadow Gateを開始する。

## Shadow中に並行実装

- Shadow Gate evaluator
- 中間quality summary
- canonical fills / TWAP / Funding merge dry-run
- episode reconstruction dry-run

## 最終Gate

以下がすべて必要:
- scheduled run success 100%
- unresolved gap 0
- cap hit 0
- checkpoint rollback 0
- sample SHA不変
- raw corruption 0
- canonical continuity error 0
- quantity mismatch 0

Gate完了まではOHLCV本分析・behavior label本適用・500-wallet expansionはHOLD。

禁止: 欠落fill推定、前方補完、wallet差替え。
