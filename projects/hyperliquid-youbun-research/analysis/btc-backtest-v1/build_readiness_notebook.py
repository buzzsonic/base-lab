#!/usr/bin/env python3
"""Build the reproducible BTC readiness audit notebook."""

from pathlib import Path

import nbformat as nbf


HERE = Path(__file__).resolve().parent


def main() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            """# BTC backtest readiness v1

## TL;DR

現存の実データは **confirmatory backtestには未準備**。このノートは仮説の成績を出すものではなく、保存済み公開データのcoverage、sampling bias、wallet集中、時間順splitを再現する品質監査である。許可範囲はexploratory split上のpipeline検証だけとする。"""
        ),
        nbf.v4.new_markdown_cell(
            """## Context and method

- raw fillsとTWAP sliceをdeduplicateしてBTC canonical fillsを作る。
- 再構成品質を通過したwalletだけを数えるが、除外率をselection biasとして明示する。
- 5/15/30/60分outcomeに必要な5分足が連続して存在するかをhorizon別に判定する。
- validationとheld-outは閾値選択に使わず、境界前60分はpurgeする。
- OI、market trades、wallet state、liquidation eventの欠測を0や推定値で補わない。"""
        ),
        nbf.v4.new_code_cell(
            """import csv
import json
from pathlib import Path

ROOT = next(
    path for path in (Path.cwd(), *Path.cwd().parents)
    if (path / "analysis/btc-backtest-v1/readiness_summary.json").exists()
)
ARTIFACT = ROOT / "analysis/btc-backtest-v1"

summary = json.loads((ARTIFACT / "readiness_summary.json").read_text(encoding="utf-8"))
splits = json.loads((ARTIFACT / "split_manifest.json").read_text(encoding="utf-8"))
with (ARTIFACT / "hypothesis_registry.csv").open(encoding="utf-8", newline="") as handle:
    hypotheses = list(csv.DictReader(handle))

summary["quality_decision"]"""
        ),
        nbf.v4.new_markdown_cell("## Data readiness results"),
        nbf.v4.new_code_cell(
            """{
    "wallets": f'{summary["eligible_wallets"]}/{summary["sample_wallets"]}',
    "excluded_wallet_rate_pct": summary["excluded_wallet_rate_pct"],
    "completed_episodes": summary["eligible_completed_episodes"],
    "btc_completed_episodes": summary["btc_completed_episodes"],
    "btc_canonical_fills": summary["btc_canonical_fills"],
    "top5_wallet_fill_share_pct": summary["top5_wallet_btc_fill_share_pct"],
    "btc_active_5m_buckets": summary["btc_active_5m_buckets"],
}"""
        ),
        nbf.v4.new_code_cell(
            """[
    {
        "horizon": horizon,
        "covered_buckets": values["buckets"],
        "coverage_pct": values["pct"],
    }
    for horizon, values in summary["outcome_coverage"].items()
]"""
        ),
        nbf.v4.new_markdown_cell("## Frozen chronological splits"),
        nbf.v4.new_code_cell(
            """{
    "splits": splits["splits"],
    "purged_at_boundaries": splits["purged_at_boundaries"],
    "status": splits["status"],
}"""
        ),
        nbf.v4.new_markdown_cell("## Hypothesis readiness (not performance)"),
        nbf.v4.new_code_cell(
            """[
    {
        "id": row["hypothesis_id"],
        "status": row["current_status"],
        "next_action": row["next_action"],
    }
    for row in hypotheses
]"""
        ),
        nbf.v4.new_markdown_cell(
            """## Takeaways

1. 100 wallet中56 walletを除外しているため、現subsetから母集団のbehavior edgeを結論しない。
2. 上位5 walletがBTC fillの72%超を占め、fill数を独立sample数として扱わない。
3. active bucketに対する60分outcome coverageは約56%。coverage不足windowはUNAVAILABLEとする。
4. historical OI、asset context、trade stream、wallet stateがない仮説はBLOCKED。推定で埋めない。
5. 次はexploratory期間だけでH02/H04/H05のoutcome-free featureとH07 outcome pipelineを実装する。held-outは開かない。"""
        ),
    ]
    nbf.write(notebook, HERE / "readiness_audit.ipynb")


if __name__ == "__main__":
    main()
