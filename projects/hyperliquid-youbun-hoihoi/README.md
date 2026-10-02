# 🪤 Hyperliquid 養分ホイホイ

公開データだけを使い、Hyperliquidで実際に活動する多様なウォレットを発見・観察・分類し、別プロジェクトの「養分くん」へ固定バージョンの研究サンプルを渡す読み取り専用パイプラインです。

このプロジェクトは養分度を採点せず、売買・署名・資金移動を一切行いません。勝敗は候補抽出条件に使いません。

## ローカルPoC

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m hoihoi.pipeline poc --limit 200
python -m unittest discover -s tests -v
```

主出力は `outputs/current/wallet_registry.parquet` と `outputs/current/research_sample.parquet`。初回候補は7日観察待ちのため、初回sampleが0件でも正常です。

## 役割境界

- 養分ホイホイ: discovery、provenance、活動確認、BOT/MM/裁定/farm疑いの分離、サンプル固定
- 養分くん: FOMO、Late、Trapped、ナンピン、Revenge、清算等の行動分析

詳細は `research_plan.md` と `PROJECT_CONTEXT.md` を参照してください。

## Daily discovery and observation

```bash
PYTHONPATH=src python -m hoihoi.collector --refresh
PYTHONPATH=src python -m hoihoi.pipeline observe --output outputs/current --refresh
```

Collector defaults to `outputs/discovery`; Actions stores captures in
`outputs/current/discovery` on `data`. A new PoC needs `--public-stream`
or captures under its output directory. Observe refreshes existing candidates only.
It preserves first_seen and requires seven distinct successful JST observation
 dates after at least seven elapsed days. Missing or saturated history blocks promotion.
Discovery runs four times daily; observation runs daily. Both persist only Hoihoi
state to `data` under a shared concurrency lock. Snapshot/weekly remain gated.
No live improvement figures have been measured for this implementation yet.
