# Realtime observation data contract

このDBは過去分析用データセットとは分離する。目的は、収集開始後の
`Late Long → Trapped → Liquidation → Cascade` を観測事実として検証できるようにすること。

## 保存ストリーム

| テーブル | 入力 | 最低限の保存内容 |
|---|---|---|
| `rt_account_state` | clearinghouse/account state | account value、withdrawable、margin used、source/ingest time |
| `rt_positions` | account state | wallet、coin、szi、entry、leverage type/value、liquidation price、uPnL、margin used |
| `rt_fills` | user fills | fill全フィールド、server order、snapshot flag |
| `rt_liquidations` | user event | event原文、wallet、coin、side、size、time |
| `rt_funding` | user funding | coin、szi、rate、USDC、time |
| `rt_trades` | public trades | coin、side、price、size、buyer/seller、time、tid |
| `rt_bbo` | BBO | bid/ask price・size、source time |
| `rt_l2` | L2 | 上下各level、price、size、order count、source time |
| `rt_asset_ctx` | asset context | mark、oracle、OI、funding、volume |
| `rt_collector_health` | collector | reconnect、gap、last message、row counts、error |

## 不変条件

- 注文・署名・秘密鍵・資金移動は実装しない。
- raw eventは変換前にappend-only保存する。
- source timeとingest timeを分ける。
- WebSocket再接続時snapshotを重複計上しない。
- gap中は状態を前方補完せず、coverageを`missing`にする。
- account stateは全ユーザー同時完全観測を保証しない。観測対象集合と選定理由をversion管理する。
- L2から正確な注文主体やicebergを推定しない。

## ラベル利用条件

- `late_entry`: entry時点以前の価格・出来高・OIだけで判定可能。
- `trapped`: 連続position stateとmark coverageが揃う区間だけ。
- `liquidated`: user eventまたは明示的なfill証拠がある場合だけ。
- `cascade`: 清算event、public trades、価格、OIの時間窓coverageが基準を満たす場合だけ。
