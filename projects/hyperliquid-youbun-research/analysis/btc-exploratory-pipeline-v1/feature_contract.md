# BTC exploratory pipeline feature contract v1

更新: 2026-10-06 JST

## Scope

固定済みexploratory期間だけで実装品質を確認する。validation / held-outは入力・閾値選択・集計に使用しない。成果物からeffect size、勝率、逆指標性、仮説採否を出さない。

## Window and missingness

- UTC連続5分windowを全件保持する。
- 品質一致44 walletは同じ固定取得期間・連続性誤差0のため、期間内wallet flowを`READY`とする。
- transition 0件は`ZERO_ACTIVITY`。source gapとは扱わない。
- 保存済みBTC 5分足がないwindowは`btc_candle_status=UNAVAILABLE`。0埋めしない。
- historical BTC asset contextがないため全eventで`feature_ready=False`。

## H02 entry concentration

- flat→positionおよびflip後の新規部分だけを`NEW`とする。ADDは混ぜない。
- wallet内の同一window NEWをVWAP化し、そのwallet価格集合からmedianと線形補間IQRを計算する。
- `entry_price_concentration_25bps`はwallet価格median±25bp内のnew-entry notional share。
- NEW 0件は価格・集中fieldを空欄NULLにする。

## H04 averaging down

- 同方向のposition増加だけをADDとする。
- add sizeが直前positionの5%以上、かつpre-add平均建値からside対称に5bp以上逆行したADDをadverseとする。
- pre-add平均建値が復元不能なら`add_state_unavailable_wallets`へ数え、adverse=0へ混ぜない。

## H05 size expansion

- walletごとにposition-increasing transitionのnotional履歴だけをpast-onlyで保持する。
- 過去20件が揃ったtransitionについて、`current increase notional / past-20 median`を連続値で保存する。
- 現段階ではsurge閾値やTRUE/FALSE labelを置かない。20件未満はNULL。

## H07 outcomes

- eventとは別fileへ、key `(sample_version, cutoff_ms, horizon_min)`で保存する。
- anchorはcutoff直前5分足close。future intervalの5分足が全本揃う場合だけ5/15/30/60分return、MFE、MAEを計算する。
- 1分足ではないためtime-to-high/lowは5分解像度としてfield名に明記する。
- outcomeをevent threshold、feature、wallet選抜へ戻さない。
