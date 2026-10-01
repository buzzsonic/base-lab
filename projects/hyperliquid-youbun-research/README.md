# Hyperliquid Youbun Research

公開データだけで「長期損失と関連する行動」を検証する独立研究モジュールです。自動売買、署名、資金移動、Discord送信は行いません。

現段階は Phase 1〜4 の PoC です。先に [research_plan.md](research_plan.md) の取得可能性と品質ゲートを確認してください。

```bash
cd projects/hyperliquid-youbun-research
python3 -m unittest discover -s tests -v
python3 -m src.poc --limit 12 --days 30 --output data
```

PoCは公式leaderboardから層別候補を選び、`userFillsByTime` をraw JSONへキャッシュし、銘柄別zero-to-zero episodeを作ります。出力は `data/` 配下で、Git管理しません。

PoCの結果は探索用です。API履歴上限、期間開始時点の持ち越し、TWAP補完、Funding、mark/candle coverageを確認するまで、勝ち負けや「逆指標」の結論には使いません。
