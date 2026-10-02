import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "audit_market_coverage.py"
SPEC = importlib.util.spec_from_file_location("audit_market_coverage", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MarketCoverageTest(unittest.TestCase):
    def test_entry_window_has_12_completed_bars_and_excludes_entry_bar(self):
        entry = 1_800_123
        bars = MODULE.expected_entry_bars(entry)
        self.assertEqual(12, len(bars))
        self.assertEqual(MODULE.floor_5m(entry) - MODULE.FIVE_MINUTES_MS, bars[-1])
        self.assertNotIn(MODULE.floor_5m(entry), bars)

    def test_future_candles_do_not_increase_past_coverage(self):
        entry = 9_000_123
        expected = MODULE.expected_entry_bars(entry)
        rows = [{"t": value} for value in expected[:-1]]
        rows += [{"t": MODULE.floor_5m(entry)}, {"t": MODULE.floor_5m(entry) + MODULE.FIVE_MINUTES_MS}]
        count, ratio = MODULE.bar_coverage(rows, expected)
        self.assertEqual(11, count)
        self.assertAlmostEqual(11 / 12, ratio)

    def test_funding_uses_only_observation_at_or_before_entry(self):
        rows = [{"time": 100, "fundingRate": "0.1"}, {"time": 200, "fundingRate": "0.2"}]
        self.assertEqual(100, MODULE.past_funding(rows, 150)["time"])
        self.assertIsNone(MODULE.past_funding(rows, 50))

    def test_floor_alignment_is_utc_epoch_based(self):
        self.assertEqual(1_800_000, MODULE.floor_5m(1_999_999))
        self.assertEqual(2_100_000, MODULE.floor_5m(2_100_000))

    def test_unavailable_ratios_are_blank_not_zero(self):
        row = {"mark_coverage_ratio": "", "oi_coverage_ratio": ""}
        self.assertEqual("", row["mark_coverage_ratio"])
        self.assertNotEqual("0", row["oi_coverage_ratio"])


if __name__ == "__main__":
    unittest.main()
