# 養分ホイホイ 実行検証 2026-10-02

## 統合と収集

- PR #14をmain@7863416b66102568c16065947bf33f89bd89ac44へsquash merge。
- 24件のunittest成功、workflow YAML parse成功、diff check成功。
- discovery run: https://github.com/buzzsonic/base-lab/actions/runs/36956559938 （success）
- 収集時間: 2026-10-02 11:38:43–11:43:43 JST。
- 主要2・アルト8・小型アルト12、計22銘柄で約定を観測。
- snapshotを含む取引3612件・ユニークwallet673件。再接続0、解析エラー0。
- 原JSONLをtime/coin/tidで重複排除し、trade.time >= started_atだけに絞って再照合した結果: 実時間取引2952件、実時間wallet598件、実時間22銘柄、小型アルト12/12銘柄。
- 原JSONL、市場snapshot、coverage manifestをdata branchへ保存。既存別プロジェクトのdataは維持。

## 観察

- observation run: https://github.com/buzzsonic/base-lab/actions/runs/36956559977
- 初回100候補の30日履歴取り込みを実行中。完了前に取得完全性・cap改善・promotion成功を主張しない。
- 同日再実行で観察日数を重複加算しないこと、API失敗時checkpointを進めないこと、Parquet往復はテスト済み。
- 1,000-wallet拡大はHOLD。snapshot/weekly本体とサンプル全体品質ゲートは次工程。
