# BTC event-study report mock — PHASE 2

更新: 2026-10-05 JST

## 目的

実収集前に、最終レポートが研究したい問いを表示できるか確認する。ここにある数値はすべてschema確認用の合成データであり、Hyperliquidの観測結果、予測、期待値ではない。

## 成果物

- `btc_event_study_report_mock.html`: 単一fileで開ける期待レポートmock
- `synthetic_events.csv`: `btc-market-event-v0.1.0`相当の120 synthetic event
- `synthetic_outcomes.csv`: 5/15/30/60分の480 synthetic outcome
- `synthetic_summary.json`: report表示値の再照合用summary
- `generate_synthetic.py`: seed固定の再生成script

## 確認ポイント

1. 養分LONG/SHORT集中とentry concentrationを同時に見られるか。
2. 条件別5/15/30/60分returnとup/down probabilityを比較できるか。
3. MFE/MAE、opposite large flow、panic exit、明示的liquidationを混同せず表示できるか。
4. optional coverage不足を0件として見せず、欠測として分離できるか。
5. 「大口が狙った」「養分は逆指標」と断定せず、観測可能なevent chainとして読めるか。

## 再生成

```bash
python3 generate_synthetic.py
```

出力はseed `20261005`でbyte-stableになる。HTMLはData report appからoffline exportしたものを配置する。
