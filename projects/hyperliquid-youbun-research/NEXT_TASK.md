# NEXT_TASK

## 軽量運用ルール

通常は最初に `STATUS_SUMMARY.md` だけ読む。
前回確認commitが分かる場合は、その後の養分くん関連commit差分だけ確認する。
`CURRENT_STATUS.md` / `DECISIONS.md` / 大きなdiffは、実装・異常調査・設計変更時だけ読む。

作業終了時に状態が変わったら、必ず `STATUS_SUMMARY.md` を最新化する。

## Current Task

研究方向を変更する。

主目的は個別walletの行動ラベル分類ではなく、**養分wallet群の集団行動と、その後の市場反応をBTCからevent-studyすること**。

詳細契約は `RESEARCH_DIRECTION.md` を正本とする。

VPS runtime package自体は実装・CI PASS済みだが、収集契約を再設計するまで本番VPS Shadowは開始しない。

## PHASE 0: BTC event-study data contract【完了】

Codexは既存collector/APIで取得可能な項目を棚卸しし、以下を「取得可能 / forwardなら取得可能 / 取得不能」に分類する。

### 養分群
- fills / TWAP / Funding
- current position size
- side
- entry price
- configured leverage
- margin mode
- liquidation price
- account equity / margin usage
- effective leverage proxy
- add / reduce / close
- realized-loss exit

### BTC市場
- price / OHLCV
- volume
- OI / OI change
- Funding
- volatility
- aggressive buy/sell flow
- large trade flow
- order-book imbalance
- liquidation flow

成果物:
- `design/btc-event-study/data_contract.md`
- `design/btc-event-study/field_matrix.csv`

欠損を推定で埋めない。APIで任意の過去stateを復元できないものはforward snapshot対象にする。

完了内容:
- 28項目を`取得可能 / forwardなら取得可能 / 取得不能`へ分類
- position/leverage/margin/liquidation price/account stateをforward snapshotへ限定
- BTC market-wide liquidation flowは公式公開APIで直接取得不能と確定

## PHASE 1: event schemaとaggregation設計【完了】

1分/5分windowを候補に、BTCについて最低限以下を定義する。

- active_youbun_wallets
- new_long_wallets / new_short_wallets
- long_notional / short_notional
- long_short_imbalance
- entry_price_mean / median / concentration
- distance_from_local_high_low
- add / averaging_down / pyramiding counts
- exit / realized_loss_exit intensity
- leverage distribution（取得可能範囲）
- liquidation-distance distribution（取得可能範囲）
- BTC return / volume / OI / Funding / volatility
- large opposite flow（取得可能なら）

future leakageを避け、entry時点で利用可能な特徴とpost-event outcomeを物理的に分離する。

成果物:
- `design/btc-event-study/event_schema.md`
- `design/btc-event-study/outcome_schema.md`

完了内容:
- 1分raw bucket、連続5分event window、5/15/30/60分outcomeを固定
- wallet transition、crowd、entry concentration、market、optional state/flowの式を定義
- event featureとpost-event outcomeを別namespaceへ物理分離
- Hoihoi handoff v0.1の受入境界とcoverage/UNAVAILABLE契約を定義

## PHASE 2: 期待レポートを先にモック化【次】

データ収集前に、最終的に欲しいレポート形式を仮データで作る。

最低限:
- 養分LONG/SHORT集中の分布
- BTC価格位置とentry集中
- leverage/size分布（取れる範囲）
- crowd concentration percentile
- 条件別5m/15m/30m/60m future return
- downside/upside probability
- MFE/MAE
- opposite large flow occurrence
- panic exit / liquidation-like flow occurrence

レポートには、例えば
「BTC上昇後・養分LONG比率高・高値近辺entry集中・OI増加・高値更新失敗」
のような複合eventを表示できる形にする。

成果物:
- `design/btc-event-study/report_mock/`

このモックを見て研究の出口が期待と一致することを確認してから、VPS収集契約を確定する。

## PHASE 3: collector v3拡張設計

PHASE 0〜2を通過した後のみ実施。

既存のUbuntu VPS + Docker + systemd timer packageを再利用し、event-studyに必要なforward snapshotを追加する。

最低限:
- fills/TWAP/Funding append-only
- BTC market series
- wallet position/account snapshots（APIで取得可能なもの）
- timestamp同期
- immutable raw
- gap/retention/checkpoint監査

収集周期は、高頻度walletのretentionだけでなくposition/account snapshot粒度も考慮して決める。

## PHASE 4: canary → Shadow

1-wallet canary → fixed-100 → 3回以上連続run。

Gate PASS後に新analysis startを固定し、7日Shadowを開始する。

## 最終的な研究問い

1. 養分walletはBTCのどの局面で片側へ偏るか
2. その時のsize/leverage/add行動はどうか
3. crowd集中後5m/15m/30m/60mの価格反応はどうか
4. OI/Funding/高値更新失敗等との複合条件で反転確率は高まるか
5. crowd集中→逆方向large flow→panic exit/liquidation-like flowというevent chainが再現するか

「大口が意図的に狙った」とは断定せず、観測可能なevent chainと条件付き確率を検証する。

## HOLD

PHASE 0〜2完了まで:
- VPS本番Shadow開始
- behavior label本適用
- 500-wallet expansion
- inverse-signal結論

は禁止。
