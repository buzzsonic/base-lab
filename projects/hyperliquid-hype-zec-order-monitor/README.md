# Hyperliquid HYPE/ZEC Order Monitor

Hyperliquid leaderboard の勝ちウォレット上位100 / 負けウォレット下位100を対象に、HYPE/ZEC周辺の未約定注文を15分ごとに監視するバッチです。

## 見ている変化

- 新規注文: 前回になく、今回ある注文ID
- 消滅注文: 前回あり、今回なくなった注文ID
- 価格帯入り: 前回は現在価格から3%以上離れていたが、今回3%以内に入った注文
- 現在の厚い帯: 現在価格から1%以内 / 3%以内に残っている注文
- net: `新規注文 - 消滅注文`
- active: 今も板に残っている未約定注文量

デフォルトの通知条件:

- 現在価格から1%以内で `$500K` 以上の新規/消滅/差分
- 現在価格から3%以内で `$1M` 以上の新規/消滅/差分
- 3%以内へ `$500K` 以上の価格帯入り/帯抜け

## 対象

`TARGET_SYMBOLS=HYPE,ZEC`

Perp の `HYPE`, `ZEC` に加えて、spotMeta から判定できる `HYPE/USDC`, `UZEC/USDC` のような関連スポットペアも対象に入ります。

## GitHub Actions

`.github/workflows/hyperliquid-hype-zec-order-monitor.yml` が毎時 7/22/37/52 分に実行します。GitHub Actions の定時実行遅延を避けるため、ちょうど 0/15/30/45 分から少しずらしています。

関連ファイルを `main` に push した時も1回実行します。通知フォーマットや閾値を変えた直後に、次の定時実行を待たず確認するためです。

Discord Webhook は GitHub Secrets に `DISCORD_WEBHOOK_URL` として設定してください。Webhook URLはリポジトリにコミットしません。

初回実行では前回スナップショットがないため、状態保存のみで変化通知は基本的に出ません。2回目以降に「新規/消滅/価格帯入り」を判定します。

## Discord通知の見方

通知は「新規/消滅」の羅列ではなく、HYPE/ZECの判断に使う集計を優先します。

```text
HYPE 現在: $62.10
判定: ロング待ち / ロング可 / 見送り
理由: BUYが近1% $650K / 3% $1.2M 残存 @61.8-62.5

■ BUY確認
勝ちBUY: active 近1% $xxx / 3% $xxx / net近 +$xxx / net3% +$xxx / 2ウォレット / @price-range
負けBUY: active 近1% $xxx / 3% $xxx / net近 -$xxx / net3% -$xxx / 1ウォレット / @price-range

■ SELL圧
勝ちSELL: active 近1% $xxx / 3% $xxx / net近 +$xxx / net3% +$xxx / 1ウォレット / @price-range
負けSELL: active 近1% $xxx / 3% $xxx / net近 +$xxx / net3% +$xxx / 3ウォレット / @price-range
```

- `active` は現在残っている注文量です
- `net近` は1%以内の `新規 - 消滅` です
- `net3%` は3%以内の `新規 - 消滅` です
- `@price-range` は3%以内に残っている注文の価格帯です
- ZECはHYPEより短く、BUY/SELLの要点だけを表示します
- 初回スナップショットは通知せず、状態保存だけ行います
- GitHub Actions では `NOTIFY_EMPTY=true` にしているため、見送り回でもHYPE/ZECの状態確認を通知します

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
