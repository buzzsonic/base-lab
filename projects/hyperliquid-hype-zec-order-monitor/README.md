# Hyperliquid HYPE/ZEC Order Monitor

Hyperliquid leaderboard の勝ちウォレット上位100 / 負けウォレット下位100を対象に、HYPE/ZEC周辺の未約定注文を15分ごとに監視するバッチです。

## 見ている変化

- 新規注文: 前回になく、今回ある注文ID
- 消滅注文: 前回あり、今回なくなった注文ID
- 価格帯入り: 前回は現在価格から3%以上離れていたが、今回3%以内に入った注文
- 現在の厚い帯: 現在価格から1%以内 / 3%以内に残っている注文

デフォルトの通知条件:

- 現在価格から1%以内で `$500K` 以上の新規/消滅/差分
- 現在価格から3%以内で `$1M` 以上の新規/消滅/差分
- 3%以内へ `$500K` 以上の価格帯入り/帯抜け

## 対象

`TARGET_SYMBOLS=HYPE,ZEC`

Perp の `HYPE`, `ZEC` に加えて、spotMeta から判定できる `HYPE/USDC`, `UZEC/USDC` のような関連スポットペアも対象に入ります。

## GitHub Actions

`.github/workflows/hyperliquid-hype-zec-order-monitor.yml` が15分おきに実行します。

Discord Webhook は GitHub Secrets に `DISCORD_WEBHOOK_URL` として設定してください。Webhook URLはリポジトリにコミットしません。

初回実行では前回スナップショットがないため、状態保存のみで変化通知は基本的に出ません。2回目以降に「新規/消滅/価格帯入り」を判定します。

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
