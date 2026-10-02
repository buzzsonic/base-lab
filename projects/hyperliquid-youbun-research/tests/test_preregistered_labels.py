import importlib.util
import json
import pathlib
import sys
import unittest
from decimal import Decimal


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "apply_preregistered_labels.py"
SPEC = importlib.util.spec_from_file_location("apply_preregistered_labels", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CONFIG = json.loads((ROOT / "labels" / "preregistered-v1" / "label_config.json").read_text())


def feature(side="LONG", **changes):
    row = {
        "side": side,
        "return_5m": "0.005",
        "return_15m": "0.012",
        "return_1h": "0.025",
        "volume_ratio_15m": "1.6",
        "range_position": "0.9" if side == "LONG" else "0.1",
        "breakout_distance": "-0.004",
        "evaluation_post_mfe": "999"
    }
    row.update(changes)
    return row


class PreregisteredLabelsTest(unittest.TestCase):
    def test_config_version_and_preregistered_status_are_fixed(self):
        self.assertEqual("1.0.0", CONFIG["config_version"])
        self.assertEqual("PREREGISTERED_BEFORE_DRY_RUN", CONFIG["status"])

    def test_long_short_direction_symmetry(self):
        long_fomo, long_late = MODULE.market_labels(feature("LONG"), CONFIG)
        short_fomo, short_late = MODULE.market_labels(feature(
            "SHORT", return_5m="-0.005", return_15m="-0.012", return_1h="-0.025"
        ), CONFIG)
        self.assertEqual("TRUE", long_fomo.status)
        self.assertEqual(long_fomo.status, short_fomo.status)
        self.assertEqual(long_late.status, short_late.status)

    def test_threshold_boundary_is_inclusive_and_fomo_late_overlap(self):
        row = feature(return_5m="0", return_15m="0.01", return_1h="0.02",
                      volume_ratio_15m="1.5", range_position="0.85", breakout_distance="-0.005")
        fomo, late = MODULE.market_labels(row, CONFIG)
        self.assertEqual("TRUE", fomo.status)
        self.assertEqual("TRUE", late.status)

    def test_missing_feature_is_unavailable_not_false(self):
        fomo, _ = MODULE.market_labels(feature(return_15m=""), CONFIG)
        self.assertEqual("UNAVAILABLE", fomo.status)
        self.assertIn("return_15m", fomo.missing)

    def test_post_entry_fields_do_not_affect_market_labels(self):
        first = MODULE.market_labels(feature(evaluation_post_mfe="1"), CONFIG)
        second = MODULE.market_labels(feature(evaluation_post_mfe="999999"), CONFIG)
        self.assertEqual(first, second)

    def test_adverse_add_and_profit_pyramid_are_symmetric(self):
        cfg = CONFIG["adds"]
        self.assertEqual("adverse", MODULE.classify_add("LONG", Decimal("100"), Decimal("99"), Decimal("10"), Decimal("100"), cfg))
        self.assertEqual("adverse", MODULE.classify_add("SHORT", Decimal("100"), Decimal("101"), Decimal("10"), Decimal("100"), cfg))
        self.assertEqual("profit", MODULE.classify_add("LONG", Decimal("100"), Decimal("101"), Decimal("10"), Decimal("100"), cfg))
        self.assertEqual("profit", MODULE.classify_add("SHORT", Decimal("100"), Decimal("99"), Decimal("10"), Decimal("100"), cfg))

    def test_small_add_is_noise(self):
        result = MODULE.classify_add("LONG", Decimal("100"), Decimal("90"), Decimal("4"), Decimal("100"), CONFIG["adds"])
        self.assertEqual("noise", result)

    def test_revenge_candidate_requires_loss_time_and_size(self):
        previous = {"average_entry": "100", "initial_size": "10", "net_pnl": "-1", "last_exit_time": "1000000", "coin": "BTC", "direction": "LONG"}
        current = {"average_entry": "100", "initial_size": "13", "first_entry_time": str(1000000 + 30 * 60000), "coin": "ETH", "direction": "SHORT"}
        result, diagnostics = MODULE.revenge_label(current, previous, CONFIG)
        self.assertEqual("TRUE", result.status)
        self.assertEqual("False", diagnostics["revenge_previous_same_coin"])
        self.assertEqual("OPPOSITE", diagnostics["revenge_side_relation"])

    def test_missing_previous_episode_is_unavailable(self):
        current = {"average_entry": "100", "initial_size": "13", "first_entry_time": "1", "coin": "ETH", "direction": "SHORT"}
        result, _ = MODULE.revenge_label(current, None, CONFIG)
        self.assertEqual("UNAVAILABLE", result.status)


if __name__ == "__main__":
    unittest.main()
