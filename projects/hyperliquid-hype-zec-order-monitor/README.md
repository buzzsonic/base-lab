# Hyperliquid Liquidation OI Monitor

Hyperliquid leaderboard の勝ちウォレット上位100 / 負けウォレット下位100を対象に、LIT/HYPE/ZEC/NEARの清算候補、OI前回比、ポジション増減を1時間ごとに監視するバッチです。

この通知はエントリー方向を決めるためのシグナルではなく、短期トレード前に「どこを割る/超えると清算が出やすいか」「前回からOIが増えて燃料が入ったか」を見るための材料です。

## 見ている変化

- 現在価格: Hyperliquid `metaAndAssetCtxs` の `markPx`
- OI: Hyperliquid全体の建玉をUSD換算した値
- OI前回比: 前回スナップショットからのOI増減
- 清算候補: 監視ウォレットの `clearinghouseState` にある `liquidationPx`
- 上側ショート清算: 価格が上がるとショートの強制買い戻しが出やすい価格帯
- 下側ロング清算: 価格が下がるとロングの強制売りが出やすい価格帯
- ポジション増減: 前回スナップショットからの勝ち/負けウォレット別Long/Short/net変化

## 対象

`TARGET_SYMBOLS=LIT,HYPE,ZEC,NEAR`

GitHub Actionsでは勝ち100 / 負け100ウォレットを取得し、そのウォレットが持つ対象銘柄のポジションから清算候補を推定します。

## GitHub Actions

`.github/workflows/hyperliquid-hype-zec-order-monitor.yml` がGitHub Actionsで自動実行します。

GitHub Actions の `schedule` で毎時7分に起動し、1回チェックして終了します。常駐ループは使いません。

関連ファイルを `main` に push した時も1回実行します。通知フォーマットや閾値を変えた直後に、次の定時実行を待たず確認するためです。

Discord Webhook は GitHub Secrets に `DISCORD_WEBHOOK_URL` として設定してください。Webhook URLはリポジトリにコミットしません。

初回実行では前回スナップショットがないため、状態保存のみで通知しません。古いスナップショットから移行した最初の1回は、OI前回比が `NA` になる場合があります。

## Discord通知の見方

```text
ZEC 現在: $521.23
OI: $235.65M / 前回比 +$4.20M (+1.81%) / Funding -0.0012%
上: ショート清算 近5%なし
下: ロング清算 @502.00 (-3.7%) $437.4K/1W
見方: OI増で燃料追加 / 下落時は表示価格割れで投げ加速警戒
ポジ増減: 勝ち net +$120.0K, L +$120.0K, S +$0, 1W / 負け net -$340.0K, L +$0, S +$340.0K, 2W
```

- `@502.00` は板にある売り注文ではなく、監視ウォレットのロング清算価格帯です
- 下側ロング清算は、その価格まで下落した時に強制売りが出やすい場所です
- 上側ショート清算は、その価格まで上昇した時に強制買い戻しが出やすい場所です
- `$437.4K` は監視ウォレットの該当ポジション量の合計です。全市場の清算量ではありません
- `W` は該当するウォレット数です
- `OI前回比 +` は建玉が増えて燃料が追加された状態、`OI前回比 -` は建玉が減って燃料が抜けた状態として見ます
- 単体の清算量だけで判断せず、現在価格からの距離、OI前回比、直近の値動きを合わせて見ます

清算量の目安:

- `$100K未満`: 基本ノイズ
- `$100K〜500K`: 監視対象
- `$500K〜2M`: 近ければ重要
- `$2M〜5M`: 強い清算帯
- `$5M以上`: かなり重要

## 環境変数

```text
DISCORD_WEBHOOK_URL=
DRY_RUN=false
NOTIFY_EMPTY=false
LEADERBOARD_LIMIT=100
TARGET_SYMBOLS=LIT,HYPE,ZEC,NEAR
LIQUIDATION_BAND_PCT=5.0
LIQUIDATION_BUCKET_PCT=0.5
MIN_LIQUIDATION_USD=100000
MIN_OI_DELTA_USD=1000000
MAX_LIQUIDATION_LEVELS=2
REQUEST_SLEEP_SECONDS=0.12
STATE_PATH=.state/hype_zec_order_snapshot.json
```

`NOTIFY_EMPTY=true` の場合、目立つ変化が少ない回でも状態確認として通知します。GitHub Actionsでは定点観測のため `true` にしています。

## ローカル実行

```bash
cp .env.example .env
# .env に DISCORD_WEBHOOK_URL を設定
python -m pip install -r requirements.txt
python -m src.main
```

通知せずに確認する場合:

```bash
DRY_RUN=true NOTIFY_EMPTY=true DISCORD_WEBHOOK_URL=dummy python -m src.main
```

## 制限

- 清算候補は監視ウォレットの `liquidationPx` から作る推定です
- Hyperliquid全市場の清算ヒートマップではありません
- リーダーボード取得はDexly公開ページに依存します
- GitHub Actionsのスケジュール実行は数分遅れる場合があります
- この通知は売買指示ではありません。IN方向、利確、損切りは別途判断してください
