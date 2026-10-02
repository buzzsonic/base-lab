import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_pilot_sampling import SAMPLE_VERSION, select


class PilotSamplingTests(unittest.TestCase):
    def rows(self):
        return [{
            "wallet": f"0x{i:040x}", "source": "hoihoi_public_trades_runtime",
            "stratum": f"s{i % 7}", "size_band": "small", "frequency_band": "low",
            "symbol_tendency": "alt", "activity_band": "jst_06_11",
        } for i in range(150)]

    def test_selection_is_deterministic_unique_and_split_before_collection(self):
        first = select(self.rows(), "seed")
        second = select(list(reversed(self.rows())), "seed")
        self.assertEqual(first, second)
        self.assertEqual(100, len(first))
        self.assertEqual(100, len({row["wallet"] for row in first}))
        counts = {name: sum(row["split"] == name for row in first)
                  for name in ("exploratory", "validation", "held_out")}
        self.assertEqual({"exploratory": 60, "validation": 20, "held_out": 20}, counts)
        self.assertTrue(all(row["sample_version"] == SAMPLE_VERSION for row in first))

    def test_script_has_no_outcome_inputs(self):
        text = (Path(__file__).parents[1] / "scripts" / "build_pilot_sampling.py").read_text()
        for forbidden in ("closedPnl", "net_pnl", "mfe", "mae", "label_v1_classification"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
