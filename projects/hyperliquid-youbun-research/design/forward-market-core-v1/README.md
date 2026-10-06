# BTC forward market core v1

これはPHASE 6の設計成果物であり、collectorの実行物ではない。

- `collector_contract.md`: 収集境界、時刻、raw/canonical、gap修復
- `contract.json`: machine-readableなstream・品質Gate定義
- `quality_gate.md`: canary開始前後の停止条件

既存のwallet collector `forward-v3` / `forward-data-v3/` は変更しない。market coreは将来実装する場合も、別entrypoint・別state・別lock・別systemd unit・別保存namespace `forward-market-core-v1/` を使う。

現時点の状態は `DESIGN_COMPLETE_NOT_IMPLEMENTED`。VPS起動、WebSocket接続、データ収集、仮説成績計算は行っていない。
