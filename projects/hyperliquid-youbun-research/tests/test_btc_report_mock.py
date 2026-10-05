import csv
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "design" / "btc-event-study" / "report_mock"


class BtcReportMockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (MOCK / "synthetic_events.csv").open(encoding="utf-8", newline="") as handle:
            cls.events = list(csv.DictReader(handle))
        with (MOCK / "synthetic_outcomes.csv").open(encoding="utf-8", newline="") as handle:
            cls.outcomes = list(csv.DictReader(handle))
        cls.summary = json.loads((MOCK / "synthetic_summary.json").read_text(encoding="utf-8"))
        cls.html = (MOCK / "btc_event_study_report_mock.html").read_text(encoding="utf-8")

    def test_synthetic_dataset_has_expected_grain(self):
        self.assertEqual(len(self.events), 120)
        self.assertEqual(len(self.outcomes), 480)
        self.assertEqual(len({row["event_id"] for row in self.events}), 120)
        self.assertEqual({int(row["horizon_min"]) for row in self.outcomes}, {5, 15, 30, 60})
        self.assertEqual({row["event_id"] for row in self.events}, {row["event_id"] for row in self.outcomes})

    def test_missing_optional_coverage_is_not_zero_filled(self):
        missing_events = [row for row in self.events if row["scenario"] == "OPTIONAL_COVERAGE_MISSING"]
        missing_outcomes = [row for row in self.outcomes if row["scenario"] == "OPTIONAL_COVERAGE_MISSING"]
        self.assertEqual(len(missing_events), 8)
        self.assertTrue(all(row["leverage_median"] == "" for row in missing_events))
        self.assertTrue(all(row["liquidation_distance_bps_median"] == "" for row in missing_events))
        self.assertTrue(all(row["opposite_large_flow_occurred"] == "" for row in missing_outcomes))
        self.assertTrue(all(row["trade_outcome_status"] == "UNAVAILABLE" for row in missing_outcomes))

    def test_summary_and_report_are_explicitly_synthetic(self):
        self.assertIs(self.summary["synthetic"], True)
        self.assertEqual(self.summary["seed"], 20261005)
        self.assertIn("SYNTHETIC REPORT MOCK", self.html)
        self.assertIn("実測値0件", self.html)
        self.assertIn("売買判断", self.html)

    def test_mock_contains_no_wallet_address(self):
        combined = "\n".join([self.html, *(str(row) for row in self.events)])
        self.assertIsNone(re.search(r"0x[a-fA-F0-9]{40}", combined))


if __name__ == "__main__":
    unittest.main()
