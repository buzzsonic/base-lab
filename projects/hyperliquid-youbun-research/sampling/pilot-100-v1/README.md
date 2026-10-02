# Pilot 100 sampling v1

Hoihoiの固定済み公開Trades runtimeを読み取り専用sourceとして、実収集開始後のtradeだけから100 walletを固定した。同一tradeは`coin/time/tid`で重複排除し、size・frequency・symbol・JST activity strataをround-robinした。

- outcome / PnL / ROI / behavior labelは抽出に不使用
- splitは収集前にexploratory 60 / validation 20 / held_out 20へ固定
- wallet差替えは禁止。技術除外はmanifestを変更せず別途記録する
- source rawはHoihoi data branchの固定commitに保持し、本ディレクトリへ複製しない
