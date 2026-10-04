# BTC research sample v0.1 dry-run

## 結論

`HOLD`。現行100件・shadow 100件のどちらからも、養分くんへ渡せるBTC research sampleは作らない。

v0.1 draftをdata commit `91c89b4`へoutcome-blindに適用した。PnL、勝率、ROI、entry後return、markout、MFE/MAEは取得・参照していない。registryやresearch sampleは変更していない。

## 集計

| Gate / quality | current | shadow |
|---|---:|---:|
| wallets | 100 | 100 |
| BTC fills 20件以上 | 41 | 33 |
| BTC active 3日以上 | 48 | 38 |
| 完結BTC episode 5件以上 | 37 | 27 |
| 上記activity 3条件すべて | 32 | 25 |
| 再構成品質clear | 51 | 59 |
| 観察日・TWAP・市場window以外の暫定Gate通過 | 0 | 2 |
| 同一ms順序不明 | 49 | 40 |
| fill history不完全 | 21 | 3 |
| TWAP証拠なし | 100 | 100 |
| 7成功JST日未達 | 100 | 100 |
| 最終handoff適格 | 0 | 0 |

shadowは履歴完全性と再構成可能性ではcurrentより良い。一方、BTC activity 3条件はcurrent 32件、shadow 25件で、small-alt改善をBTC研究適格性の改善とは扱えない。暫定2件もTWAP未取得、7日未達、高値飛び乗り用市場window未結合のためsampleへ昇格しない。

## 発見した品質問題

### TWAP evidence unavailable

Hoihoi checkpointは`userFillsByTime`だけを保存し、別endpointの`userTwapSliceFillsByTime`を保存していない。TWAPが無かったとは判断できないため、全200件を`TWAP_EVIDENCE_UNAVAILABLE`とした。

### Same-millisecond order was not preserved

現行checkpoint生成はdeduplicate後に`(time, row hash)`でsortする。同一timestampのserver orderが失われるため、複数BTC fillが同一msにあるcurrent 49件・shadow 40件は順序不明とした。この影響下のcontinuity errorやquantity mismatchをwallet行動として解釈しない。

### High-price-chase unavailable

entry以前のBTC市場windowを結合していないため、全walletで`high_price_chase_candidate=UNAVAILABLE`。entry後価格を使った補完はしない。

## 再現

`scripts/dry_run_btc_sample.py`へdata branch上のcurrent / shadow directoryを渡す。詳細なwallet別`selection_audit.parquet`と集計`summary.json`を別出力へ生成する。出力はsampleではなく監査結果である。

## 次の品質ゲート

1. Hoihoi checkpointでAPIの同一timestamp返却順を保持する。既存hash順データは修復せずlegacy扱いにする。
2. `userTwapSliceFillsByTime`を別raw sourceとして追加し、通常fillと観測済み`startPosition`鎖で統合する。
3. 新しいforward windowで最低7成功JST日を観察する。
4. entry以前のBTC market windowだけをprofile入力として結合する。
5. v0.1を再実行し、適格walletをoutcome-blind目視確認してからhandoff versionを固定する。
