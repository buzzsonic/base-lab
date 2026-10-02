import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "build_past_features.py"
SPEC = importlib.util.spec_from_file_location("build_past_features", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def candles(start=0, count=12):
    return [
        {"t": start + index * MODULE.FIVE_MINUTES_MS, "o": str(100 + index), "h": str(102 + index),
         "l": str(99 + index), "c": str(101 + index), "v": str(index + 1)}
        for index in range(count)
    ]


class PastFeaturesTest(unittest.TestCase):
    def test_exact_window_excludes_entry_and_future_rows(self):
        entry = 12 * MODULE.FIVE_MINUTES_MS + 123
        rows = candles()
        rows.extend([{"t": 12 * MODULE.FIVE_MINUTES_MS, "o": "999", "h": "999", "l": "999", "c": "999", "v": "999"}])
        window = MODULE.exact_window(rows, entry)
        self.assertEqual(12, len(window))
        self.assertEqual("112", window[-1]["c"])

    def test_missing_one_bar_rejects_entire_window(self):
        entry = 12 * MODULE.FIVE_MINUTES_MS + 123
        self.assertIsNone(MODULE.exact_window(candles()[:-1], entry))

    def test_duplicate_timestamp_rejects_entire_window(self):
        entry = 12 * MODULE.FIVE_MINUTES_MS + 123
        rows = candles()
        rows.append(dict(rows[-1]))
        self.assertIsNone(MODULE.exact_window(rows, entry))

    def test_returns_use_open_and_close_inside_requested_lookback(self):
        window = candles()
        self.assertAlmostEqual(112 / 111 - 1, MODULE.price_return(window, 1))
        self.assertAlmostEqual(112 / 109 - 1, MODULE.price_return(window, 3))
        self.assertAlmostEqual(112 / 100 - 1, MODULE.price_return(window, 12))

    def test_volume_ratios_have_past_baselines(self):
        window = candles()
        self.assertAlmostEqual(12 / 6, MODULE.volume_ratio(window, 1))
        self.assertAlmostEqual((10 + 11 + 12) / ((sum(range(1, 10)) / 9) * 3), MODULE.volume_ratio(window, 3))

    def test_short_breakout_is_positive_below_prior_low(self):
        window = candles()
        window[-1]["c"] = "90"
        result = MODULE.local_structure(window, "SHORT")
        self.assertGreater(result["breakout_distance"], 0)

    def test_null_formatter_never_turns_missing_into_zero(self):
        self.assertEqual("", MODULE.fmt(None))
        self.assertNotEqual("0", MODULE.fmt(None))


if __name__ == "__main__":
    unittest.main()
