# Hyperliquid HYPE/ZEC Order Monitor

Hyperliquid leaderboard の勝ちウォレット上位100 / 負けウォレット下位100を対象に、HYPE/ZECの売買判断、ポジション増減、未約定注文を1時間ごとに監視するバッチです。

## 見ている変化

- HYPE売買判断: `SMA6 > SMA12` ならロング、`SMA6 <= SMA12` ならノーポジ
- ZEC売買判断: `SMA6 > SMA24` ならロング、`SMA6 < SMA24` ならショート
- 現在ポジション: 勝ち/負けウォレット別のLong/Short総額と平均建値
- ポジション増減: 前回スナップショットからのLong側/Short側/net変化
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

`.github/workflows/hyperliquid-hype-zec-order-monitor.yml` がGitHub Actionsで自動実行します。

GitHub Actions の `schedule` で毎時7分に起動し、1回チェックして終了します。通知頻度を落としてノイズを減らすため、常駐ループは使いません。

関連ファイルを `main` に push した時も1回実行します。通知フォーマットや閾値を変えた直後に、次の定時実行を待たず確認するためです。

Discord Webhook は GitHub Secrets に `DISCORD_WEBHOOK_URL` として設定してください。Webhook URLはリポジトリにコミットしません。

初回実行では前回スナップショットがないため、状態保存のみで変化通知は基本的に出ません。2回目以降に「新規/消滅/価格帯入り」を判定します。

## Discord通知の見方

通知は「SMAによる売買判断」を最初に出し、その下に勝ち/負けウォレットのポジション増減を残します。未約定注文は最後の補足です。

```text
HYPE $71.66
判断: ロング
条件: SMA6 $70.8 > SMA12 $69.4 / 6h +3.2%
出る/切替: SMA6 <= SMA12
理由: SMA6がSMA12を上回る

■ ポジション増減
勝ち: net +$4.2M / Long側 +$5.1M / Short側 +$900.0K / 6W
負け: net -$1.8M / Long側 +$400.0K / Short側 +$2.2M / 9W

■ 現在ポジ
勝ち: Long $18.4M avg $64.2 (3W) / Short $3.1M avg $69.8 (1W)
負け: Long $5.2M avg $68.1 (2W) / Short $12.8M avg $66.4 (5W)
注文補足: BUY近 $420.0K / 3% $1.1M / net3 +$200.0K | SELL近 $390.0K / 3% $900.0K / net3 -$100.0K
```

- `判断` は売買方向です。HYPEはロング/ノーポジ、ZECはロング/ショートで見ます
- `ポジション増減` の `net` はLong側増加からShort側増加を差し引いた値です
- `W` は変化したウォレット数です
- `現在ポジ` は勝ち/負けウォレット別のLong/Short総額と平均建値です
- `注文補足` は未約定注文の残量とnetです。判断の主役ではなく補助として見ます
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
