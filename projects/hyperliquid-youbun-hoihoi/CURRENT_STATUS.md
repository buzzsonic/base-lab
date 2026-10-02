# CURRENT_STATUS

更新: 2026-10-02 JST（PR #14統合、discovery実行・保存成功、日次観察実行中）

口座分類・cap率の表はIssue #8時点のbaseline。日次観察の結果は完了後に更新する。

| item | state |
|---|---|
| active wallets | 0（7日観察前の即時昇格は禁止） |
| candidate wallets | 100（200-wallet discovery poolから層化選抜） |
| excluded wallets | 0（物理削除はしない） |
| arbitrage suspected | 1（通常sample候補から分離） |
| BOT suspected | 38（旧52から改善） |
| MM suspected | 9（旧17から改善） |
| farm suspected | 1 |
| latest snapshot | NOT RUN |
| latest weekly run | NOT RUN（再PoCのみ） |
| last successful GitHub Action | `36956559938`（discovery・data保存、success） |
| known issues | userFills 2,000件capは63%。小型アルト中心は2%。既存public Trades captureの時点・銘柄coverageは限定的 |
| current blockers | 7日観察期間未経過。初回100候補の増分履歴取り込みは実行中。1,000-wallet拡大は引き続き保留 |

## Issue #8 再PoC結果

| 指標 | 旧100件 | 層化後100件 |
|---|---:|---:|
| userFills 2,000件cap | 84% | 63% |
| BOT疑い | 52% | 38% |
| MM疑い | 17% | 9% |
| inactive | 14% | 15% |
| 高頻度 | 67% | 48% |
| 中頻度 | 16% | 30% |
| 低頻度 | 17% | 22% |
| 重複 | 0% | 0% |

層化後の規模帯は小口30・中口52・大口3・不明15。銘柄傾向はBTC/ETH中心38・アルト中心45・小型アルト中心2・不明15。JST活動時間帯は各6時間帯18〜24件（inactive由来の不明15）。Leaderboard順位帯はtop 1%=12、top 10%=17、middle 40%=23、bottom 50%=11、非Leaderboard=37。

高頻度/BOT偏重は明確に改善したが、cap 63%と小型アルト2%はまだ弱い。Issue #8の「改善確認」は通過、1,000件拡大ゲートは未通過と判断する。

## 2026-10-02 次工程の実装

- 未統合collectorブランチの実装を取り込み、JST 4時間帯・主要/アルト/小型アルトの取得と市場snapshot保存を追加。
- userFillsByTimeを時間区間分割し、walletごとの増分checkpoint・重複排除・取得budgetを実装。
- 同一msの2,000件飽和、10,000件retention到達、未取得区間を不完全として保持。API失敗時はcheckpointを進めない。
- 日次observeで既存candidateを再観察し、first_seenを維持。7日経過かつ7 JST日分の完全取得を昇格条件にする。同日再実行は重複カウントしない。
- discovery/observeは共通concurrencyでdata branchへ対象ディレクトリだけを保存。push競合時にforce pushしない。
- 検証: 24件のテスト成功、workflow YAML構文確認成功。実API取得・Actions運用・cap率改善は未検証。
- この変更で既存の100件/63%/2%という実測値は更新していない。1,000-wallet拡大はHOLDを維持。

## PR #14 運用検証

- mainへ統合済み（merge commit `7863416`）。
- discovery run `36956559938` はsuccess。data branch `4fea9437aac3036f7fb64abc74ae37e23a7e906a`へraw・市場snapshot・coverageを保存。
- 22/22銘柄、小型アルト12/12銘柄、snapshotを含むwallet673件を観測。
- 原JSONL照合: 接続直後の過去取引を除いた実時間2952取引・598wallet、実時間の小型アルト12/12銘柄。再接続0・解析エラー0。
- observation run `36956559977` は初回100候補の履歴取り込み中。約定取得の完全性・cap率改善・観察保存はまだ未確認。
- 詳細: `QUALITY_REPORT_RUNTIME_2026_10_02.md`。
