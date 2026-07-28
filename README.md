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

`main` 側のリポジトリ直下にある `dataget` を使う。毎回 `fetch` してから読むので**常に最新**。

```bash
./dataget cohorts | tail -5      # コホートL/S(毎時)
./dataget spread | tail -3       # 実効ドル円ほか(15分毎、当月)
./dataget spread 2026-08         # 月を指定
./dataget state                  # 平日FXレートのキャッシュ
./dataget ls                     # このブランチのファイル一覧
```

中身は `git fetch origin data && git show origin/data:<パス>` を1行にまとめただけ。

**worktree は張らないこと。** `git worktree add ../base-lab-data data` で常設フォルダを
作る手もあるが、自動では更新されないので `pull` を忘れると古いデータで分析してしまう。
しかもファイルは普通に存在するためエラーが出ず、間違いに気づけない。
このデータは毎時・15分毎に増えるので、その事故が起きやすい。
毎回リモートから読む方式なら構造的に起きない。
