# data ブランチ

**収集器が追記するデータ専用のブランチ。コードは入っていない。**

`main` にデータを積むと1日120コミット（spread-logger 96 + cohort-snapshot 24）で
履歴が埋まり、コードの差分が追えなくなるため分離した。

## 中身

| パス | 収集器 | 頻度 | 内容 |
|---|---|---|---|
| `spread-logger/data/YYYY-MM.csv` | Spread Logger | 15分 | 国内4取引所×HLの価格・FR・実効ドル円乖離 |
| `spread-logger/.state/spread_logger_state.json` | Spread Logger | 15分 | **平日FXレートのキャッシュ**とアラートのクールダウン |
| `coin-scout/data/cohorts.jsonl` | Cohort Snapshot | 毎時 | HyperdashのコホートL/S＋同時刻のHL参照価格 |

パスは `main` 側の `projects/<名前>/` 以下と対応している（`projects/` の階層だけ落としてある）。

## 仕組み

各ワークフローは以下の順で動く。**復元を飛ばすと追記先が空ファイルになり、
過去のデータが毎回上書きで消える**ので、順序を変えないこと。

1. `main` をチェックアウト（コード）
2. `data` ブランチを `_databranch/` へチェックアウト
3. **復元** — `_databranch/<名前>/` から作業ディレクトリへコピー
4. 収集器を実行（既存ファイルへ追記）
5. **書き戻し** — 作業ディレクトリから `_databranch/<名前>/` へコピー
6. `_databranch` でコミットし `data` ブランチへpush

`.state` の平日FXレートは週末の実効ドル円を計算する基準なので、
3の復元が効いていないと週末データが壊れる。

## 読み方

```bash
git fetch origin data
git show origin/data:coin-scout/data/cohorts.jsonl | tail -5
```

作業ツリーを汚さずに常時参照したいなら worktree を張る。

```bash
git worktree add ../base-lab-data data
```
