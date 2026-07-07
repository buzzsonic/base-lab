# spread-logger

国内取引所×Hyperliquidの価格・ファンディングの歪みを15分毎に記録し、閾値超えのみDiscordに通知するボット。
仕様と経緯は [KICKOFF.md](KICKOFF.md) を参照。

## 何をするか

GitHub Actionsで15分毎に以下を実行する:

1. **価格取得** — 国内4取引所(bitFlyer/bitbank/GMOコイン/Coincheck)の公開ティッカーAPIから
   BTC/ETH/XRP/SOL/DOGE/LTCのJPYペアのbest bid/askを取得(各取引所の未上場ペアは黙ってスキップ)。
   Hyperliquid info APIからパープのmid/funding、現物(HYPE/UBTC/UETH/USOL)のmidを取得。
   USDJPY参照レートを open.er-api.com から取得(週末は平日に保存した最新値=金曜終値を使う)。
2. **乖離計算**
   - 実効ドル円 = 国内mid ÷ HLパープmid、参照USDJPYからの乖離%
   - 国内取引所間クロス(bestbid > bestaskの最良組み合わせ)
   - HL現物-パープのベーシス%(HYPE/UBTC/UETH/USOL)
   - FR年率換算%(funding_hourly × 24 × 365 × 100)
3. **CSV追記** — `data/YYYY-MM.csv` に1実行1行(固定スキーマ、初回にヘッダ書き込み)
4. **Discordアラート** — 閾値超え(`.env.example`参照)のみ通知。同一種別×銘柄は`ALERT_COOLDOWN_HOURS`(既定6時間)クールダウン。
   実行が全滅した場合はエラー通知。事実の報告のみで売買推奨はしない。

自動売買はしない。通知とCSV記録のみ。

## 取引所ごとの実際の対応ペア(2026-07時点で実機確認済み)

| 銘柄 | bitFlyer | bitbank | GMOコイン | Coincheck |
|------|----------|---------|-----------|-----------|
| BTC  | ○ | ○ | ○ | ○ |
| ETH  | ○ | ○ | ○ | ○ |
| XRP  | ○ | ○ | ○ | ○ |
| SOL  | ✕(product未対応) | ○ | ○ | ○ |
| DOGE | ✕(product未対応) | ○ | ○ | ○ |
| LTC  | ✕(product未対応) | ○ | ○ | ✕(404、非対応) |

bitFlyerは `/v1/markets` を毎回叩いて対応product_codeを動的判定しているため、対応銘柄が増えれば自動的に拾う。
Coincheckは公式ドキュメント上btc_jpy以外のtickerを謳っていないが、実際には `?pair=` でETH/XRP/SOL/DOGEも有効な
JSON(bid/ask込み)を返す。LTCのみ404 HTMLが返るため非対応と判定している。

## Hyperliquid現物mid取得の注意(ハマりどころ)

`spotMetaAndAssetCtxs` の `assetCtxs` 配列は、実機確認したところ `universe` のリスト順と対応していない
(全く違う価格になる)。一方 `allMids` の `"@{pair_index}"` キーは実勢と整合する。そのため本プロジェクトでは
`spot_meta()`(pair_index → "BASE/QUOTE" の対応表)と `all_mids()`(価格そのもの)を組み合わせて現物midを取得している
(`src/fetch_hyperliquid.py`)。

## ローカル実行

```sh
cd projects/spread-logger
PYTHONPATH=../.. DRY_RUN=true python -m src.main
```

環境変数は `.env.example` を参照。閾値・銘柄セットはすべて環境変数で調整できる。

## 状態ファイル

`.state/spread_logger_state.json` に以下を保存する:

- `fx` — 直近の平日に取得したUSDJPY参照レート(週末はこれを「金曜終値」として使い回す)
- `alerts` — アラート種別×銘柄ごとの最終発火時刻(クールダウン管理)

coin-scout等と異なり、このプロジェクトは `.state/` と `data/` をGitにコミットして永続化する
(プロジェクト直下の `.gitignore` でルートの `.state/` 除外を打ち消している)。
