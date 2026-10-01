# CURRENT_STATUS

更新: 2026-10-02 JST（Issue #8 層化再PoC・main反映・Discord通知完了）

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
| last successful GitHub Action | `36928323512`（専用Discord完了通知、success） |
| known issues | userFills 2,000件capは63%。小型アルト中心は2%。既存public Trades captureの時点・銘柄coverageは限定的 |
| current blockers | 7日観察期間未経過。専用discovery collector未実装。1,000-wallet拡大は引き続き保留 |

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
