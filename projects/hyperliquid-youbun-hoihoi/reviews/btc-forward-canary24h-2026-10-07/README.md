# BTC forward canary 24h Gate

判定日: 2026-10-07 JST  
対象期間: 2026-10-06 00:15:45〜2026-10-07 00:15:45 JST  
判定: **FAIL / 7日window昇格禁止**

## 結論

通常fills / TWAPの別raw保存、API返却順、overlap first-seen、BTC position chainの経路は実データで確認できた。一方、GitHub Actions scheduleが数時間単位で欠落し、BTC 5分市場windowのcoverageが26.7%に留まった。連続24時間の研究windowとして使用できない。

## Gate結果

| check | evidence | result |
|---|---:|---|
| collector run | 5 / expected 73 slots | FAIL |
| max run gap | 413.8分（上限40分） | FAIL |
| final tail gap | 367.0分（上限40分） | FAIL |
| BTC 5m coverage | 77 / 288 = 26.7% | FAIL |
| endpoint failure / cap / source gap | 0 / 0 / 0 | PASS |
| TWAP raw | 2,499 | PASS |
| overlap duplicate | 180 | PASS |
| source order failure | 0 | PASS |
| BTC position rows | 46 | PASS |
| same-ms ambiguity / continuity error | 0 / 0 | PASS |

rawは3,299件、first-seen canonicalは3,119件。180件のoverlap重複をrawに残したままcanonicalで先着rowを維持した。

## Wallet別の注意

Hoihoi暫定候補 `0x7b2d...1522` は24時間でfills 3件、TWAP 0件、BTC position row 0件だった。この1日だけで恒久除外はしないが、7日研究cohortの対象として必要なBTC短期活動性は確認できなかった。

残る4件は収集経路検証専用であり、BOT / MM / arbitrage / farm除外Gateを通していない。TWAPが観測されたことをsample適格性と解釈しない。

## 影響と次工程

- workflowは監査後に`disabled_manually`へ停止した。
- このwindowを成功JST日として数えない。
- sample昇格、7日cohort開始、100/200/1,000 wallet拡大はHOLD。
- 次はGitHub scheduleを使わず、single-flightの外部timerで新namespaceの24時間canaryを再実行する。
- 次回候補は開始直前の公開BTC Tradesで活動を確認し、outcomeを見ずに固定する。

監査は `scripts/audit_btc_forward_canary24h.py` で再実行できる。
