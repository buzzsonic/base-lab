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

## Public Trades discovery collector

専用collectorは公式WebSocketの公開`trades`だけを読み取り、JST 00/06/12/18時台にBTC/ETH・主要アルト・小型アルトを別枠で収集します。小型アルトは日付・時間帯ごとに決定論的にローテーションします。

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m hoihoi.collector --duration 300 --refresh
```

各runは `outputs/discovery/date=YYYY-MM-DD/window=jst_HH_HH/run=.../` にraw JSONLと`coverage.json`を保存します。GitHub Actionsはこのpartitionを30日artifactとして保持します。data branchへのcommitは永続化統合テストが通るまで行いません。

## 役割境界

- 養分ホイホイ: discovery、provenance、活動確認、BOT/MM/裁定/farm疑いの分離、サンプル固定
- 養分くん: FOMO、Late、Trapped、ナンピン、Revenge、清算等の行動分析

詳細は `research_plan.md` と `PROJECT_CONTEXT.md` を参照してください。
