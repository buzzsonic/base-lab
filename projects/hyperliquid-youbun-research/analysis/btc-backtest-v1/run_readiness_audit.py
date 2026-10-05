#!/usr/bin/env python3
"""Audit whether existing real data can support BTC hypothesis backtests.

This script is read-only with respect to source data. It writes only aggregated,
address-free audit artifacts to its output directory.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import hashlib
import json
from collections import Counter
from pathlib import Path


JST = dt.timezone(dt.timedelta(hours=9))
FIVE_MIN_MS = 5 * 60 * 1000
PURGE_MS = 60 * 60 * 1000
SPLIT_1_MS = int(dt.datetime(2026, 9, 21, tzinfo=JST).timestamp() * 1000)
SPLIT_2_MS = int(dt.datetime(2026, 9, 27, tzinfo=JST).timestamp() * 1000)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wallet_from_raw_name(path: Path) -> str:
    marker = path.name.index("0x")
    return path.name[marker : marker + 42].lower()


def split_name(timestamp_ms: int) -> str | None:
    if timestamp_ms < SPLIT_1_MS - PURGE_MS:
        return "exploratory"
    if SPLIT_1_MS <= timestamp_ms < SPLIT_2_MS - PURGE_MS:
        return "validation"
    if timestamp_ms >= SPLIT_2_MS:
        return "held_out"
    return None


def pct(numerator: int | float, denominator: int | float) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def load_canonical_btc_fills(raw_dir: Path, eligible_wallets: set[str]):
    rows = []
    seen = set()
    for source, pattern in (("fills", "fills_*.json"), ("twap", "twap_fills_*.json")):
        for filename in sorted(glob.glob(str(raw_dir / pattern))):
            path = Path(filename)
            wallet = wallet_from_raw_name(path)
            if wallet not in eligible_wallets:
                continue
            for fill in read_json(path):
                if fill.get("coin") != "BTC":
                    continue
                key = fill.get("tid") or (
                    fill.get("time"), fill.get("hash"), fill.get("oid"),
                    fill.get("px"), fill.get("sz"),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"wallet": wallet, "source": source, **fill})
    rows.sort(key=lambda row: (int(row["time"]), str(row.get("tid", ""))))
    return rows


def hypothesis_rows(summary: dict) -> list[dict[str, str]]:
    active = summary["btc_active_5m_buckets"]
    return [
        {
            "hypothesis_id": "BTC-H01",
            "version": "v1",
            "hypothesis": "養分LONG/SHORT集中後の価格反応",
            "required_fields": "BTC fills/TWAP; startPosition; BTC OHLCV; BTC asset context",
            "current_status": "BLOCKED_CORE",
            "current_evidence": f"BTC fills {summary['btc_canonical_fills']}; active 5m buckets {active}; BTC asset-context/OI snapshots 0",
            "exploratory_rule": "imbalance percentileはexploratoryだけで選ぶ",
            "primary_outcomes": "5/15/30/60m return; MFE; MAE",
            "regimes": "bull/bear/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "asset context欠測windowはfeature_ready=False",
            "next_action": "forward BTC asset contextを収集後にevent table生成",
        },
        {
            "hypothesis_id": "BTC-H02",
            "version": "v1",
            "hypothesis": "entry価格帯集中後の価格反応",
            "required_fields": "new-entry transitions; entry px/notional; BTC OHLCV; BTC asset context",
            "current_status": "DERIVABLE_NOT_BUILT",
            "current_evidence": f"stable raw transition fieldsあり; active 5m buckets {active}; entry concentration aggregate未生成",
            "exploratory_rule": "25bps concentrationとIQRを連続値で保持しpercentile探索",
            "primary_outcomes": "5/15/30/60m return; MFE; MAE",
            "regimes": "bull/bear/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "new-entryがないwindowは0件、source gapはUNAVAILABLE",
            "next_action": "new-entry transition aggregatorを実装しasset context待ち",
        },
        {
            "hypothesis_id": "BTC-H03",
            "version": "v1",
            "hypothesis": "local high/low付近での飛び乗り後の反転",
            "required_fields": "new-entry transitions; prior 60m BTC OHLCV; future BTC OHLCV",
            "current_status": "PARTIAL_EXPLORATORY_ONLY",
            "current_evidence": f"future 60m OHLCV coverage {summary['outcome_coverage_pct']['60m']}% of active buckets; full-period coverageなし",
            "exploratory_rule": "high/low距離とprior return閾値はexploratoryだけで調整",
            "primary_outcomes": "5/15/30/60m return; reversal probability; MFE; MAE",
            "regimes": "trend/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "prior 12 barsまたはfuture bars不足はUNAVAILABLE",
            "next_action": "連続OHLCV範囲内だけでpipeline検証。採否判断は禁止",
        },
        {
            "hypothesis_id": "BTC-H04",
            "version": "v1",
            "hypothesis": "averaging down集中後の価格反応",
            "required_fields": "ordered fills/TWAP; pre-add average; add px/size; BTC OHLCV",
            "current_status": "DERIVABLE_NOT_BUILT",
            "current_evidence": "startPosition chainあり; pilot-100用add event table未生成",
            "exploratory_rule": "adverse distanceとposition増加率を連続値で保持",
            "primary_outcomes": "5/15/30/60m return; MFE; MAE; panic-exit count",
            "regimes": "bull/bear/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "順序一意でないchainはUNAVAILABLE",
            "next_action": "pilot-100 rawからoutcome-free add evidenceを生成",
        },
        {
            "hypothesis_id": "BTC-H05",
            "version": "v1",
            "hypothesis": "position size急拡大後の価格反応",
            "required_fields": "ordered BTC fills/TWAP; pre/post position; BTC OHLCV",
            "current_status": "DERIVABLE_NOT_BUILT",
            "current_evidence": "sz/startPositionあり; window-level size expansion未生成",
            "exploratory_rule": "wallet内baseline比とcross-wallet percentileを分離",
            "primary_outcomes": "5/15/30/60m return; MFE; MAE",
            "regimes": "bull/bear/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "baseline履歴不足walletはUNAVAILABLE",
            "next_action": "past-only size baselineを実装",
        },
        {
            "hypothesis_id": "BTC-H06",
            "version": "v1",
            "hypothesis": "crowd集中とOI/Funding/Volume複合条件",
            "required_fields": "crowd event; BTC OI; Funding; candle volume",
            "current_status": "BLOCKED_OI",
            "current_evidence": f"historical OI 0%; Funding prior-2h coverage {summary['funding_prior_2h_coverage_pct']}%; candle volumeはOHLCV範囲のみ",
            "exploratory_rule": "複合条件は単変量結果を確認後に事前登録",
            "primary_outcomes": "5/15/30/60m return; MFE; MAE",
            "regimes": "OI up/down; Funding sign/extreme; volume percentile",
            "minimum_sample": "各condition-side cell>=50; total>=500",
            "missingness_rule": "OI欠測は0にせずUNAVAILABLE",
            "next_action": "forward asset context/OI seriesが必要",
        },
        {
            "hypothesis_id": "BTC-H07",
            "version": "v1",
            "hypothesis": "5/15/30/60m returnとMFE/MAE",
            "required_fields": "complete future BTC 5m candles",
            "current_status": "PARTIAL_EXPLORATORY_ONLY",
            "current_evidence": f"active bucket future coverage: 5m {summary['outcome_coverage_pct']['5m']}%, 60m {summary['outcome_coverage_pct']['60m']}%",
            "exploratory_rule": "全horizonを同時報告し都合の良いhorizonだけ選ばない",
            "primary_outcomes": "return; upside/downside probability; MFE; MAE",
            "regimes": "bull/bear/range; high/low volatility",
            "minimum_sample": "event>=100 and control>=100; independent JST days>=10",
            "missingness_rule": "必要future barが1本でも欠けたhorizonはUNAVAILABLE",
            "next_action": "連続OHLCV範囲内でoutcome pipelineだけ検証",
        },
        {
            "hypothesis_id": "BTC-H08",
            "version": "v1",
            "hypothesis": "反対方向large flow出現後の価格反応",
            "required_fields": "BTC trade stream; aggressor side; past-only p99 threshold",
            "current_status": "BLOCKED_NO_TRADES",
            "current_evidence": "pilot-100期間のmarket trade streamなし",
            "exploratory_rule": "p99 thresholdはcutoff以前60mだけで固定",
            "primary_outcomes": "flow occurrence; subsequent return; MFE; MAE",
            "regimes": "crowd side; price trend; volatility",
            "minimum_sample": "flow event>=100; independent JST days>=10",
            "missingness_rule": "trade stream gapはFALSEでなくUNAVAILABLE",
            "next_action": "forward BTC tradesが必要",
        },
        {
            "hypothesis_id": "BTC-H09",
            "version": "v1",
            "hypothesis": "panic exit / liquidation-like flowのevent chain",
            "required_fields": "cohort reductions; realized-loss exits; explicit liquidation event/fill; BTC trades",
            "current_status": "PARTIAL_PANIC_ONLY",
            "current_evidence": f"completed BTC episodes {summary['btc_completed_episodes']}; explicit liquidation observed {summary['explicit_liquidations_observed']}; userEventsなし",
            "exploratory_rule": "panic exitとexplicit liquidationを別metricにする",
            "primary_outcomes": "panic-exit wallet count; explicit liquidation count; subsequent return",
            "regimes": "crowd side; adverse move; volatility",
            "minimum_sample": "event chain>=100 or descriptive-only",
            "missingness_rule": "通常の損失closeをliquidationへ読み替えない",
            "next_action": "panic-exit候補は導出可能。liquidation chainはforward event収集待ち",
        },
    ]


def run_audit(repo_root: Path, source_root: Path, market_root: Path, output_dir: Path) -> dict:
    sampling_path = repo_root / "sampling/pilot-100-v1/sampling_manifest.csv"
    audit_path = repo_root / "reviews/pilot-100-reconstruction-audit-2026-10-03/wallet_audit.csv"
    episodes_path = source_root / "processed/position_episodes.csv"
    candles_path = market_root / "candles_5m_BTC_reference.json"
    funding_path = market_root / "funding_BTC.json"

    sampling = read_csv(sampling_path)
    wallet_audit = {row["anon_wallet_id"]: row for row in read_csv(audit_path)}
    eligible = {
        row["wallet"].lower(): row
        for row in sampling
        if wallet_audit[row["anon_wallet_id"]]["eligible"] == "True"
    }

    episodes = [
        row for row in read_csv(episodes_path)
        if row["wallet"].lower() in eligible
        and row["closed"] == "True"
        and row["left_censored"] == "False"
    ]
    btc_episodes = [row for row in episodes if row["coin"] == "BTC"]
    btc_fills = load_canonical_btc_fills(source_root / "raw", set(eligible))
    active_buckets = sorted({int(row["time"]) // FIVE_MIN_MS * FIVE_MIN_MS for row in btc_fills})
    candles = read_json(candles_path)
    candle_times = {int(row["t"]) for row in candles}
    funding = read_json(funding_path)
    funding_times = sorted(int(row["time"]) for row in funding)

    horizon_coverage = {}
    for horizon in (5, 15, 30, 60):
        count = 0
        for bucket in active_buckets:
            cutoff = bucket + FIVE_MIN_MS
            required = [cutoff + offset * FIVE_MIN_MS for offset in range(horizon // 5)]
            count += int(all(timestamp in candle_times for timestamp in required))
        horizon_coverage[f"{horizon}m"] = {"buckets": count, "pct": pct(count, len(active_buckets))}

    funding_covered = 0
    for bucket in active_buckets:
        cutoff = bucket + FIVE_MIN_MS
        funding_covered += int(any(cutoff - 2 * 60 * 60 * 1000 <= time <= cutoff for time in funding_times))

    wallet_fill_counts = Counter(row["wallet"] for row in btc_fills)
    split_counts = {}
    for name in ("exploratory", "validation", "held_out"):
        episode_rows = [row for row in episodes if split_name(int(row["first_entry_time"])) == name]
        btc_episode_rows = [row for row in btc_episodes if split_name(int(row["first_entry_time"])) == name]
        buckets = [bucket for bucket in active_buckets if split_name(bucket + FIVE_MIN_MS) == name]
        split_counts[name] = {
            "all_completed_episodes": len(episode_rows),
            "btc_completed_episodes": len(btc_episode_rows),
            "btc_active_5m_buckets": len(buckets),
            "independent_jst_days": len({
                dt.datetime.fromtimestamp(bucket / 1000, JST).date().isoformat() for bucket in buckets
            }),
        }

    purged_counts = {
        "all_completed_episodes": sum(split_name(int(row["first_entry_time"])) is None for row in episodes),
        "btc_completed_episodes": sum(split_name(int(row["first_entry_time"])) is None for row in btc_episodes),
        "btc_active_5m_buckets": sum(split_name(bucket + FIVE_MIN_MS) is None for bucket in active_buckets),
    }

    all_entry_times = [int(row["first_entry_time"]) for row in episodes]
    btc_entry_times = [int(row["first_entry_time"]) for row in btc_episodes]
    summary = {
        "audit_version": "btc-backtest-readiness-v1",
        "generated_at": "2026-10-06T00:00:00+09:00",
        "source_kind": "existing real Hyperliquid public data",
        "sample_wallets": len(sampling),
        "eligible_wallets": len(eligible),
        "excluded_wallets": len(sampling) - len(eligible),
        "excluded_wallet_rate_pct": pct(len(sampling) - len(eligible), len(sampling)),
        "eligible_completed_episodes": len(episodes),
        "btc_completed_episodes": len(btc_episodes),
        "btc_long_episodes": sum(row["direction"] == "LONG" for row in btc_episodes),
        "btc_short_episodes": sum(row["direction"] == "SHORT" for row in btc_episodes),
        "btc_canonical_fills": len(btc_fills),
        "btc_twap_only_fills": sum(row["source"] == "twap" for row in btc_fills),
        "btc_wallets_with_fills": len(wallet_fill_counts),
        "btc_active_5m_buckets": len(active_buckets),
        "active_jst_days": len({dt.datetime.fromtimestamp(bucket / 1000, JST).date().isoformat() for bucket in active_buckets}),
        "period_start_jst": dt.datetime.fromtimestamp(min(all_entry_times) / 1000, JST).isoformat(),
        "period_end_jst": dt.datetime.fromtimestamp(max(all_entry_times) / 1000, JST).isoformat(),
        "btc_period_start_jst": dt.datetime.fromtimestamp(min(btc_entry_times) / 1000, JST).isoformat(),
        "btc_period_end_jst": dt.datetime.fromtimestamp(max(btc_entry_times) / 1000, JST).isoformat(),
        "top1_wallet_btc_fill_share_pct": pct(wallet_fill_counts.most_common(1)[0][1], len(btc_fills)),
        "top5_wallet_btc_fill_share_pct": pct(sum(count for _, count in wallet_fill_counts.most_common(5)), len(btc_fills)),
        "btc_candle_rows": len(candles),
        "btc_candle_start_jst": dt.datetime.fromtimestamp(min(candle_times) / 1000, JST).isoformat(),
        "btc_candle_end_jst": dt.datetime.fromtimestamp(max(candle_times) / 1000, JST).isoformat(),
        "outcome_coverage": horizon_coverage,
        "outcome_coverage_pct": {key: value["pct"] for key, value in horizon_coverage.items()},
        "funding_rows": len(funding),
        "funding_prior_2h_coverage_buckets": funding_covered,
        "funding_prior_2h_coverage_pct": pct(funding_covered, len(active_buckets)),
        "historical_btc_oi_coverage_pct": 0.0,
        "historical_btc_asset_context_coverage_pct": 0.0,
        "historical_btc_trade_stream_coverage_pct": 0.0,
        "historical_wallet_state_coverage_pct": 0.0,
        "explicit_liquidations_observed": sum(row["liquidation_observed"] == "True" for row in btc_episodes),
        "split_counts": split_counts,
        "purged_counts": purged_counts,
        "quality_decision": "NOT_READY_FOR_CONFIRMATORY_BACKTEST",
        "exploratory_allowance": "PIPELINE_VALIDATION_ONLY",
        "blocking_reasons": [
            "56% wallet exclusion creates material sampling bias",
            "top five wallets contribute more than 70% of eligible BTC fills",
            "BTC asset context and historical OI coverage are 0%",
            "BTC trade stream and wallet-state snapshot coverage are 0%",
            "future 60m OHLCV covers only part of active buckets",
            "existing wallet-based splits are severely imbalanced and are replaced by time splits",
        ],
        "source_sha256": {
            "sampling_manifest": sha256(sampling_path),
            "wallet_audit": sha256(audit_path),
            "position_episodes": sha256(episodes_path),
            "btc_candles": sha256(candles_path),
            "btc_funding": sha256(funding_path),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "readiness_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    hypotheses = hypothesis_rows(summary)
    with (output_dir / "hypothesis_registry.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(hypotheses[0]))
        writer.writeheader()
        writer.writerows(hypotheses)

    split_manifest = {
        "split_version": "btc-time-split-v1",
        "timezone": "Asia/Tokyo",
        "maximum_outcome_horizon_minutes": 60,
        "purge_rule": "exclude the final 60 minutes before each boundary",
        "splits": [
            {"name": "exploratory", "start": summary["period_start_jst"], "end_exclusive": "2026-09-20T23:00:00+09:00", **split_counts["exploratory"]},
            {"name": "validation", "start": "2026-09-21T00:00:00+09:00", "end_exclusive": "2026-09-26T23:00:00+09:00", **split_counts["validation"]},
            {"name": "held_out", "start": "2026-09-27T00:00:00+09:00", "end_exclusive": summary["period_end_jst"], **split_counts["held_out"]},
        ],
        "purged_at_boundaries": purged_counts,
        "status": "BOUNDARIES_FROZEN_COUNTS_NOT_CONFIRMATORY_READY",
        "notes": [
            "Splits are chronological and replace the old wallet-based 60/20/20 assignment for market event-study.",
            "Held-out data must not be inspected for threshold selection.",
            "The current data remains biased and incomplete; these boundaries do not authorize confirmatory conclusions.",
        ],
    }
    (output_dir / "split_manifest.json").write_text(
        json.dumps(split_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = f"""# BTC backtest readiness v1

更新: 2026-10-06 JST

## 結論

**現存データはconfirmatory backtestに使用不可。exploratoryのpipeline検証だけ許可する。**

品質一致subsetは{summary['eligible_wallets']}/100 wallet、完結episode {summary['eligible_completed_episodes']:,}件、BTC {summary['btc_completed_episodes']:,}件。数量不一致・連続性誤差は0だが、56 wallet除外によるselection biasが残る。さらにBTC fillの上位5 wallet依存率は{summary['top5_wallet_btc_fill_share_pct']:.2f}%で、独立sample数をfill件数のまま解釈できない。

## Datasetとgrain

- source: Hyperliquid公開fills / TWAP / Fundingと保存済みBTC 5分足
- raw対象期間: {summary['period_start_jst']} 〜 {summary['period_end_jst']}
- BTC canonical fills: {summary['btc_canonical_fills']:,}件（TWAP-only {summary['btc_twap_only_fills']:,}件）
- BTC取引wallet: {summary['btc_wallets_with_fills']} / eligible {summary['eligible_wallets']}
- BTC activity: {summary['btc_active_5m_buckets']:,} active 5分bucket / {summary['active_jst_days']} JST日
- intended grain: 全連続5分market window。現在はevent table未生成

## Core findings

| finding | evidence | severity | downstream impact |
|---|---:|---|---|
| wallet selection bias | 100中56 wallet除外 | Critical | 母集団のbehavior-performance結論は禁止 |
| wallet concentration | BTC fills上位1 wallet {summary['top1_wallet_btc_fill_share_pct']:.2f}%、上位5 wallet {summary['top5_wallet_btc_fill_share_pct']:.2f}% | High | naiveなfill/event数は独立sample数を過大評価 |
| BTC OHLCV outcome不足 | active bucketの60m outcome coverage {summary['outcome_coverage_pct']['60m']:.2f}% | High | 全期間のreturn/MFE/MAE比較不可 |
| OI / asset context欠測 | historical coverage 0% | Critical | schema準拠feature_ready eventは0 |
| market trade stream欠測 | historical coverage 0% | High | opposite large flow仮説を検証不可 |
| wallet state欠測 | historical coverage 0% | High | leverage/liquidation-distance仮説を検証不可 |
| liquidation evidence不足 | BTC explicit liquidation観測 {summary['explicit_liquidations_observed']}件、userEventsなし | High | 損失closeを清算へ読み替え禁止 |

## Outcome coverage

| horizon | covered active buckets | coverage |
|---:|---:|---:|
"""
    for horizon in ("5m", "15m", "30m", "60m"):
        report += f"| {horizon} | {summary['outcome_coverage'][horizon]['buckets']:,} | {summary['outcome_coverage_pct'][horizon]:.2f}% |\n"
    report += f"""

Fundingはcutoff以前2時間内の観測があるactive bucketで{summary['funding_prior_2h_coverage_pct']:.2f}%だが、OIが0%のためOI/Funding/Volume複合仮説は`BLOCKED_OI`とする。

## 時間順split

旧sampling manifestのwallet別splitはBTC episodeがexploratoryへ偏るため、market event-studyには使用しない。最大outcome 60分に合わせ、各境界直前60分をpurgeする。

| split | BTC active 5m buckets | independent JST days | status |
|---|---:|---:|---|
| exploratory | {split_counts['exploratory']['btc_active_5m_buckets']:,} | {split_counts['exploratory']['independent_jst_days']} | pipeline検証のみ |
| validation | {split_counts['validation']['btc_active_5m_buckets']:,} | {split_counts['validation']['independent_jst_days']} | 未開封扱い |
| held_out | {split_counts['held_out']['btc_active_5m_buckets']:,} | {split_counts['held_out']['independent_jst_days']} | 未開封扱い |

境界直前60分のpurgeにより、全coin完結episode {purged_counts['all_completed_episodes']:,}件、BTC完結episode {purged_counts['btc_completed_episodes']:,}件、BTC active bucket {purged_counts['btc_active_5m_buckets']:,}件をいずれのsplitにも含めない。境界は`split_manifest.json`へ固定した。ただしdata自体がconfirmatory-readyではないため、分割を作ったことはvalidation開始の許可を意味しない。

## 仮説別status

- `BLOCKED_CORE`: H01。BTC asset context/OIがなくschema準拠eventを作れない。
- `DERIVABLE_NOT_BUILT`: H02、H04、H05。raw transitionから導出可能だが集計table未生成。
- `PARTIAL_EXPLORATORY_ONLY`: H03、H07。保存済みOHLCVの連続範囲でpipeline検証のみ可能。
- `BLOCKED_OI`: H06。historical OI 0%。
- `BLOCKED_NO_TRADES`: H08。BTC trade stream 0%。
- `PARTIAL_PANIC_ONLY`: H09。panic-exit候補は導出可能だがliquidation chainは不可。

詳細は`hypothesis_registry.csv`を正本とする。

## 次の最小実装

1. held-outへ触れず、exploratory期間だけでBTC 5分event aggregatorを実装する。
2. 全windowを保持し、zero-activity windowとsource-gapを区別する。
3. H02/H04/H05のoutcome-free featureを生成する。
4. OHLCVが揃う区間でH07 outcome pipelineだけを検証する。
5. H01/H06/H08/H09の不足seriesはcollector追加要件として明示し、現データで推定しない。

## Source provenance

source fileのSHA-256は`readiness_summary.json`へ保存した。raw wallet addressは成果物へ出力していない。
"""
    (output_dir / "data_readiness.md").write_text(report, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--market-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run_audit(args.repo_root, args.source_root, args.market_root, args.output_dir)
    print(json.dumps({
        "quality_decision": summary["quality_decision"],
        "eligible_wallets": summary["eligible_wallets"],
        "btc_completed_episodes": summary["btc_completed_episodes"],
        "btc_active_5m_buckets": summary["btc_active_5m_buckets"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
