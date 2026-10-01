# PROJECT_CONTEXT — 養分くん

## 目的

Hyperliquidの公開データを用い、長期損失と関連する典型的なトレーダー行動を集団として検証する研究プロジェクト。個人攻撃やウォレット晒しは目的にしない。

最終目標は、FOMO、Late Long/Short、Trapped Trader、含み損ナンピン、Revenge Trade、Size Up After Win、Crowded Positioning、Liquidation Cluster、Liquidation Cascadeと損益・市場変化の関係を、費用・Funding・欠測・バイアスを含めて検証すること。統計的に有効なら、将来のリアルタイム「養分センサー」へ進む。

## 研究上の原則

- 自動売買BOTではない。注文、署名、資金移動を実装しない。
- 観測事実、再構成値、仮説を分離し、相関を因果と呼ばない。
- 結論ありきで「養分は逆指標」と決めない。
- fill単位ではなく、銘柄別zero-to-zero position episodeを基本単位にする。
- fee・Funding・部分決済・追加・反転・同一時刻順序・欠測を明示する。
- 品質ゲート通過前にFOMO/Late/Nanpin/Revenge等の成績結論へ進まない。

## 過去分析とリアルタイム観測

過去分析ではEntry/Exit、PnL、position size、holding time、FOMO、Late Entry、ナンピン、Revenge、price、volume、OI、Fundingを扱う。任意の過去margin状態、清算価格、清算直前equityは無理に推定しない。

リアルタイム観測ではaccount state、leverage、liquidation price/events、fills、funding、trades、BBO/L2を継続保存し、将来の `Late Long → Trapped → Liquidation → Cascade` を検証する。詳細は `REALTIME_DATA_CONTRACT.md`。

## 重要なデータ制約

- `userFillsByTime`、TWAP、ordersには履歴・件数上限がある。
- candleは直近5,000本で、5分足は約17日分。
- 過去のcross-margin口座状態は完全復元できない。
- leaderboardだけではwhale、bot/MM、spot中心、無活動口座が混ざる。
- WebSocket切断区間は前方補完せず欠測扱いにする。

## セキュリティと既存資産

- 公開・読み取り専用データのみ使用する。
- 秘密鍵、APIキー、Webhook URLをコードやGitへ保存しない。
- 既存BOT・既存DB・通知workflowを変更しない。本研究は独立モジュールとして維持する。
