import csv
import importlib.util
import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/btc-exploratory-pipeline-v1"
SUMMARY = ARTIFACT / "pipeline_summary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("btc_pipeline", ARTIFACT / "build_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BtcExploratoryPipelineTest(unittest.TestCase):
    def test_outputs_are_exploratory_only(self):
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(summary["split"], "exploratory")
        self.assertEqual(summary["validation_or_held_out_rows_processed"], 0)
        self.assertFalse(summary["hypothesis_performance_computed"])
        self.assertEqual(summary["core_feature_ready_rows"], 0)

    def test_event_and_outcome_are_physically_separate_and_unique(self):
        with (ARTIFACT / "events_exploratory.csv").open(encoding="utf-8", newline="") as handle:
            events = list(csv.DictReader(handle))
        with (ARTIFACT / "outcomes_exploratory.csv").open(encoding="utf-8", newline="") as handle:
            outcomes = list(csv.DictReader(handle))
        self.assertNotIn("future_return", events[0])
        self.assertNotIn("mfe_up", events[0])
        self.assertNotIn("mae_down", events[0])
        self.assertIn("future_return", outcomes[0])
        event_keys = {(row["sample_version"], row["cutoff_ms"]) for row in events}
        outcome_keys = {(row["sample_version"], row["cutoff_ms"], row["horizon_min"]) for row in outcomes}
        self.assertEqual(len(event_keys), len(events))
        self.assertEqual(len(outcome_keys), len(outcomes))
        self.assertEqual(len(outcomes), 4 * len(events))

    def test_continuous_windows_and_zero_activity_are_preserved(self):
        with (ARTIFACT / "events_exploratory.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        starts = [int(row["window_start_ms"]) for row in rows]
        self.assertTrue(all(right - left == 300_000 for left, right in zip(starts, starts[1:])))
        zero_rows = [row for row in rows if row["wallet_activity_status"] == "ZERO_ACTIVITY"]
        self.assertGreater(len(zero_rows), 0)
        self.assertTrue(all(row["wallet_flow_status"] == "READY" and row["active_youbun_wallets"] == "0" for row in zero_rows))

    def test_unavailable_candles_and_outcomes_are_blank_not_zero(self):
        with (ARTIFACT / "events_exploratory.csv").open(encoding="utf-8", newline="") as handle:
            unavailable = next(row for row in csv.DictReader(handle) if row["btc_candle_status"] == "UNAVAILABLE")
        self.assertEqual(unavailable["btc_close"], "")
        with (ARTIFACT / "outcomes_exploratory.csv").open(encoding="utf-8", newline="") as handle:
            unavailable_outcome = next(row for row in csv.DictReader(handle) if row["price_outcome_status"] == "UNAVAILABLE")
        self.assertEqual(unavailable_outcome["future_return"], "")
        self.assertEqual(unavailable_outcome["mfe_up"], "")
        self.assertEqual(unavailable_outcome["mae_down"], "")

    def test_add_classification_is_side_symmetric_and_past_only(self):
        module = load_module()
        self.assertEqual(module.classify_add("LONG", Decimal("100"), Decimal("99"), Decimal("1"), Decimal("10")), "ADVERSE")
        self.assertEqual(module.classify_add("SHORT", Decimal("100"), Decimal("101"), Decimal("1"), Decimal("10")), "ADVERSE")
        self.assertEqual(module.classify_add("LONG", None, Decimal("99"), Decimal("1"), Decimal("10")), "UNAVAILABLE")

    def test_artifacts_contain_no_wallet_addresses(self):
        address = re.compile(r"0x[a-fA-F0-9]{40}")
        for path in ARTIFACT.iterdir():
            if path.suffix in {".csv", ".json", ".md"}:
                self.assertIsNone(address.search(path.read_text(encoding="utf-8")), path.name)
