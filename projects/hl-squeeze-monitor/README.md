# Hyperliquid Squeeze Monitor

Hyperliquidで取引可能なperpetualだけを母集団に、Binance Futures / Bybit Futures / Hyperliquidの価格・Open Interest・Funding・出来高を5分ごとに照合するDiscord監視Botです。注文機能、秘密鍵、取引用APIキーはありません。通知は売買推奨ではありません。

## 検知

- SHORT SQUEEZE候補: 価格上昇 + OI増加 + Funding低下
- LONG SQUEEZE候補: 価格下落 + OI増加 + Funding上昇
- Level 1: Funding 0.03%/h、OI 1h +5%、価格が方向一致、出来高1.3xのうち3条件
- Level 2: Funding 0.08%/h、OI 1h +10%、価格1h 1%、出来高1.5x、Funding悪化をすべて満たす
- Level 3: Funding 0.15%/h、OI 1h +12%、価格1h 3%、出来高2.5x、高安値break、2取引所以上一致
- Level 4: Funding 0.30%/h、OI 24h +50%、価格6h 15%、出来高3x

スコアはFunding 30、異常度10、OI 25、価格15、出来高15、取引所一致10、breakout 5を上限100へ丸めます。Level判定とスコアを併用し、同一Levelは抑制します。6時間後かつスコアが15以上悪化した場合のみ再通知します。Level 2以上からLevel 0へ戻ると解除通知します。

## Fundingの単位

内部値と環境変数はすべて「1時間あたりの小数」です。`-0.0003` は `-0.03%/hour` です。Binanceは公開値を8時間で割り、Bybitは銘柄別`fundingInterval`（分）で割り、Hyperliquidはもともとの1時間率を使います。intervalを無視した比較はしません。

## データとmapping

Hyperliquid `metaAndAssetCtxs`、Binance USD-M Futures public API、Bybit v5 linear public APIを使います。`BTC -> BTCUSDT`の完全一致を基本とし、`kPEPE -> 1000PEPEUSDT`など明示aliasだけを許可します。曖昧な推測mappingは通知漏れを選び、誤対応を避けます。最低24h出来高はHyperliquid側$1Mです。

## 実行

```bash
cd projects/hl-squeeze-monitor
python -m pip install -r requirements.txt
DEBUG=true MAX_SYMBOLS=10 PYTHONPATH=../.. python -m src.main
pytest -q
```

GitHubのSettings > Secrets and variables > Actionsへ`DISCORD_WEBHOOK_URL`を登録します。Actionsの`HL Squeeze Monitor`から手動実行もできます。cronは`*/5 * * * *`ですが、GitHub Actionsは開始時刻を厳密には保証しません。

## 状態保存と制約

`.state/state.json`に約24時間分（最大300点）のsnapshot、Level、score、通知時刻を保存し、Actions cacheで次回へ渡します。cacheは永続DBではなく、削除・競合・初回run時には履歴がwarm-upします。5m/15m/1h/6h/24h変化は十分なsnapshotが貯まるまで`N/A`です。Funding異常度もsnapshotが6点未満なら無効です。1取引所障害時は残りで続行しますが、Hyperliquid母集団を取得できない場合は誤通知防止のため停止します。
