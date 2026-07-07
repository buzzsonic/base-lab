# coin-scout

「狙い目コイン」を検知してDiscordに通知するスクリーニングボット。
仕様と経緯は [KICKOFF.md](KICKOFF.md) を参照。

## 何をするか

1日2回(8:00 / 20:00 JST、GitHub Actions)、以下を実行する:

1. **監視対象の選定** — Hyperliquid上場銘柄のうち、BinanceまたはBybitの24h出来高が$10M以上、
   またはCoinGecko集計出来高が$20M以上の銘柄(流動性フィルタ。超マイナー銘柄を構造的に除外)。
   GitHub Actionsランナー(米国IP)ではBybit(403)とBinance先物(451)が地域ブロックされるため、
   Binance現物は公式ミラー data-api.binance.vision を使い、CoinGeckoがBybit分の実質代替になる。
   Coinglass APIも検討したが無料キーでは市場一覧系エンドポイントが全て使えず見送り(有料プランなら差し替え候補)
2. **検知3本柱**
   - 出来高急増: 24h出来高が直近7日平均の2倍以上 + 24h価格変動±5%以上
   - ファンディング偏り: 年率換算±30%以上(方向の示唆付き)
   - OI急増: 前回スキャン比+20%以上(OI $5M以上の銘柄のみ)
   - 新規上場: Hyperliquid銘柄一覧の前回との差分(警告付き)
3. **Discordダイジェスト通知** — 発火銘柄ゼロでも「該当なし」を送る(生存確認を兼ねる)。実行エラーもDiscordに通知

自動売買はしない。通知のみ。

## ローカル実行

```sh
cd projects/coin-scout
PYTHONPATH=../.. DRY_RUN=true python -m src.main
```

環境変数は `.env.example` を参照。閾値はすべて環境変数で調整できる。

## 状態ファイル

`.state/scout_state.json` に前回スキャンの銘柄一覧とOIを保存する
(OI変化と新規上場の判定に使用)。GitHub Actionsでは actions/cache で永続化。
初回実行時はこの2つの判定がスキップされる。
