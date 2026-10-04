# BTC research sample contract v0.1 draft

## 目的と境界

養分ホイホイが、養分くんのBTC event-studyへ渡す研究対象walletをoutcome-blindに選抜するための事前契約。
walletの発見・分類・品質管理・handoffまでを扱う。BTC価格帯、市場局面、entry後return、markout、PnL比較、逆指標判定は扱わない。

本versionは既存cohortへのdry-run前のdraftであり、まだ実sampleを生成しない。dry-run結果を見て同じversionの閾値を変更してはならない。変更時は新versionを作る。

## 選抜Gate

全条件を満たしたwalletだけが`ELIGIBLE`。

| Gate | v0.1 draft |
|---|---:|
| 成功観察 | 7 JST日以上 |
| BTC active day | 3日以上 |
| BTC fills | 20件以上 |
| 完結BTC zero-to-zero episode | 5件以上 |
| profile集計の最低根拠 | 3 episode |
| 未解消gap / continuity error / quantity mismatch | すべて0 |
| page cap / TWAP cap | どちらも未到達 |
| BOT / MM / arbitrage / funding arbitrage / farm | すべて非該当 |

20 fills・5 episode・3 active daysはPoC用の丸い初期値であり、成果や価格反応から最適化した値ではない。資産額、PnL、勝率、ROI、将来価格は選抜に使わない。

`add_fill_count=0`は除外理由ではない。完全なordered fillsから「追加が無かった」と判定できることが重要であり、追加行動の存在を必須にするとナンピンwalletを意図的に過剰抽出するためである。

## 行動profile

- `high_price_chase_candidate`: 養分くんのpreregistered-v1 FOMO定義を再利用する。entry以前のBTC価格・出来高だけを使用し、past-only windowが無ければ`UNAVAILABLE`。
- `averaging_down_candidate`: 既存positionの5%以上を、LONGでは事前平均建値より5bp以上低く、SHORTでは5bp以上高く追加したepisodeを数える。
- `size_surge_candidate`: 直前5完結BTC episodeのinitial notional中央値に対し2倍以上のinitial notional。直前5件が無ければ`UNAVAILABLE`。

profileは`TRUE / FALSE / UNAVAILABLE`の三値。欠測を`FALSE`や0へ変換しない。`candidate`は行動の観測分類であり、損失、意図、感情、将来価格の予測を意味しない。

## 成果物

1. `selection_audit.parquet`: 候補全wallet。Gate値、`ELIGIBLE/EXCLUDED/UNAVAILABLE`、複数の除外理由を保持。
2. `btc_research_sample.json`: `handoff_schema.json`準拠の適格walletのみ。version、source snapshot、quality、BTC activity、profile、episode referenceを保持。
3. `handoff_manifest.json`: 各成果物のSHA-256、生成コードcommit、入力data commit、件数、schema version。

養分くんはhandoffを自動採用しない。schema検証、hash一致、selection version許可、重複wallet/episodeなしを確認してから別versionの分析sampleとして受け入れる。

## Episode reference

`first_entry_time_ms`と`last_exit_time_ms`はUTC epoch milliseconds。`side`、size、fill種別件数、entry VWAPを渡し、養分くんが別途保持するBTC市場系列と結合できるようにする。Hoihoi handoffにentry後return、MFE、MAE、PnL、勝敗を追加してはならない。

## 次の検証

1. 現行100件とshadow 100件からBTC専用activity/episode項目を作る。
2. Gateをdry-runし、適格数と除外理由をcohort別に報告する。
3. TRUE/FALSE/UNAVAILABLEを層別に目視照合する。
4. 同一入力でbyte-identicalな成果物を確認する。
5. 養分くん側でexample handoffの受入テストを行う。
