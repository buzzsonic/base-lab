import csv
import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/btc-backtest-v1"


def load_summary():
    return json.loads((ARTIFACT / "readiness_summary.json").read_text(encoding="utf-8"))


def load_splits():
    return json.loads((ARTIFACT / "split_manifest.json").read_text(encoding="utf-8"))


class BtcBacktestReadinessTest(unittest.TestCase):
    def test_readiness_decision_and_observed_counts_are_frozen(self):
        summary = load_summary()
        self.assertEqual(summary["quality_decision"], "NOT_READY_FOR_CONFIRMATORY_BACKTEST")
        self.assertEqual(summary["exploratory_allowance"], "PIPELINE_VALIDATION_ONLY")
        self.assertEqual(summary["eligible_wallets"], 44)
        self.assertEqual(summary["excluded_wallets"], 56)
        self.assertEqual(summary["eligible_completed_episodes"], 22_973)
        self.assertEqual(summary["btc_completed_episodes"], 10_125)
        self.assertEqual(summary["btc_canonical_fills"], 69_708)

    def test_split_counts_plus_purge_reconcile_to_totals(self):
        summary = load_summary()
        splits = summary["split_counts"]
        purged = summary["purged_counts"]
        self.assertEqual(sum(row["all_completed_episodes"] for row in splits.values()) + purged["all_completed_episodes"], summary["eligible_completed_episodes"])
        self.assertEqual(sum(row["btc_completed_episodes"] for row in splits.values()) + purged["btc_completed_episodes"], summary["btc_completed_episodes"])
        self.assertEqual(sum(row["btc_active_5m_buckets"] for row in splits.values()) + purged["btc_active_5m_buckets"], summary["btc_active_5m_buckets"])

    def test_split_manifest_keeps_held_out_closed_for_threshold_selection(self):
        manifest = load_splits()
        self.assertEqual(manifest["status"], "BOUNDARIES_FROZEN_COUNTS_NOT_CONFIRMATORY_READY")
        self.assertTrue(any("must not be inspected" in note for note in manifest["notes"]))
        self.assertEqual(manifest["purged_at_boundaries"], load_summary()["purged_counts"])

    def test_all_priority_hypotheses_are_registered_with_missingness_rules(self):
        with (ARTIFACT / "hypothesis_registry.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["hypothesis_id"] for row in rows], [f"BTC-H{i:02d}" for i in range(1, 10)])
        self.assertTrue(all(row["version"] == "v1" and row["missingness_rule"] for row in rows))
        status = {row["hypothesis_id"]: row["current_status"] for row in rows}
        self.assertEqual(status["BTC-H06"], "BLOCKED_OI")
        self.assertEqual(status["BTC-H08"], "BLOCKED_NO_TRADES")

    def test_published_artifacts_do_not_contain_wallet_addresses(self):
        address = re.compile(r"0x[a-fA-F0-9]{40}")
        for name in ("readiness_summary.json", "split_manifest.json", "hypothesis_registry.csv", "data_readiness.md"):
            self.assertIsNone(address.search((ARTIFACT / name).read_text(encoding="utf-8")))

    def test_split_function_purges_each_boundary_hour(self):
        spec = importlib.util.spec_from_file_location("readiness", ARTIFACT / "run_readiness_audit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.split_name(module.SPLIT_1_MS - module.PURGE_MS - 1), "exploratory")
        self.assertIsNone(module.split_name(module.SPLIT_1_MS - module.PURGE_MS))
        self.assertEqual(module.split_name(module.SPLIT_1_MS), "validation")
        self.assertIsNone(module.split_name(module.SPLIT_2_MS - module.PURGE_MS))
        self.assertEqual(module.split_name(module.SPLIT_2_MS), "held_out")
