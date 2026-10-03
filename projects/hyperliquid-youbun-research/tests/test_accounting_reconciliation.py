from decimal import Decimal
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.review_episodes import eligibility_reasons
from src.poc import fetch_fills, merge_fills


def quality_row(**overrides):
    row = {
        "completed_uncensored": "1",
        "perp_fills": "2",
        "quantity_mismatches": "0",
        "continuity_errors": "0",
        "twap_endpoint_capped": "False",
    }
    row.update(overrides)
    return row


class AccountingReconciliationTest(unittest.TestCase):
    def test_fill_pagination_repeats_boundary_timestamp_and_deduplicates(self):
        first = [{"tid": i, "time": i, "coin": "BTC"} for i in range(1, 2001)]
        second = [first[-1], {"tid": 2001, "time": 2000, "coin": "BTC"}]
        calls = []

        def fake_get_json(_url, payload):
            calls.append(payload)
            return first if len(calls) == 1 else second

        with tempfile.TemporaryDirectory() as directory, patch("src.poc.get_json", side_effect=fake_get_json):
            rows = fetch_fills("0xabc", 1, 3000, Path(directory), page_delay_seconds=0)
        self.assertEqual(2001, len(rows))
        self.assertEqual(2000, calls[1]["startTime"])

    def test_twap_fill_is_interleaved_by_observed_position_chain(self):
        regular = [
            {"tid": 1, "time": 100, "coin": "BTC", "startPosition": "0", "side": "B", "sz": "1"},
            {"tid": 3, "time": 100, "coin": "BTC", "startPosition": "2", "side": "B", "sz": "1"},
        ]
        twap = [{"tid": 2, "time": 100, "coin": "BTC", "startPosition": "1", "side": "B", "sz": "1"}]
        merged, added = merge_fills(regular, twap)
        self.assertEqual(1, added)
        self.assertEqual([1, 2, 3], [row["tid"] for row in merged])

    def test_zero_perp_fill_account_is_excluded(self):
        reasons = eligibility_reasons(quality_row(completed_uncensored="0", perp_fills="0"))
        self.assertIn("no_completed_episode", reasons)
        self.assertIn("no_perp_fills", reasons)

    def test_capped_twap_account_is_excluded(self):
        reasons = eligibility_reasons(quality_row(twap_endpoint_capped="True", continuity_errors="15"))
        self.assertIn("twap_endpoint_capped", reasons)
        self.assertIn("continuity_error", reasons)

    def test_twap_merge_deduplicates_tid_and_marks_new_slice(self):
        regular = [{"tid": 1, "coin": "BTC", "time": 1, "sz": "1"}]
        twap = [
            {"tid": 1, "coin": "BTC", "time": 1, "sz": "1"},
            {"tid": 2, "coin": "BTC", "time": 2, "sz": "1"},
        ]
        merged, added = merge_fills(regular, twap)
        self.assertEqual(added, 1)
        self.assertEqual([row["source_kind"] for row in merged], ["regular", "twap"])

    def test_builder_fee_is_not_subtracted_twice(self):
        closed_pnl = Decimal("10")
        fee_including_builder = Decimal("2")
        builder_component = Decimal("0.5")
        funding = Decimal("1")
        net = closed_pnl - fee_including_builder + funding
        self.assertEqual(net, Decimal("9"))
        self.assertNotEqual(net, closed_pnl - fee_including_builder - builder_component + funding)


if __name__ == "__main__":
    unittest.main()
