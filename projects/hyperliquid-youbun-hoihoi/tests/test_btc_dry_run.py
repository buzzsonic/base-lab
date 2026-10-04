import json
import tempfile
import unittest
from pathlib import Path

from hoihoi.btc_dry_run import analyze_btc_fills, audit_cohort
from hoihoi.storage import write_parquet


def fill(time, start, side, size, px="100"):
    return {"coin": "BTC", "time": time, "startPosition": start, "side": side, "sz": size, "px": px}


class BtcDryRunTests(unittest.TestCase):
    def test_reconstructs_complete_episode_and_add(self):
        metrics = analyze_btc_fills([
            fill(1, "0", "B", "1"),
            fill(2, "1", "B", "0.5", "99"),
            fill(3, "1.5", "A", "0.5", "101"),
            fill(4, "1", "A", "1", "102"),
        ])
        self.assertEqual(metrics["completed_btc_episodes"], 1)
        self.assertEqual(metrics["add_fill_count"], 1)
        self.assertEqual(metrics["quantity_mismatch_count"], 0)

    def test_same_millisecond_order_is_ambiguous(self):
        metrics = analyze_btc_fills([fill(1, "0", "B", "1"), fill(1, "1", "A", "1")])
        self.assertEqual(metrics["ambiguous_same_ms_rows"], 1)
        self.assertEqual(metrics["averaging_down_candidate"], "UNAVAILABLE")

    def test_audit_fails_closed_without_twap_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            wallet = "0x" + "1" * 40
            write_parquet(path / "wallet_registry.parquet", [{
                "wallet": wallet, "successful_observation_days": 7,
                "bot_suspected": False, "mm_suspected": False,
                "arbitrage_suspected": False, "funding_arbitrage_suspected": False,
                "farm_suspected": False,
            }])
            checkpoint = {"complete": True, "gaps": [], "fills": []}
            target = path / "fill-checkpoints" / f"{wallet}.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(checkpoint))
            rows, summary = audit_cohort(path, "test")
            self.assertEqual(rows[0]["eligibility"], "UNAVAILABLE")
            self.assertIn("TWAP_EVIDENCE_UNAVAILABLE", rows[0]["exclusion_reasons"])
            self.assertEqual(summary["handoff_eligible"], 0)
            self.assertEqual(summary["preliminary_pass_excluding_observation_twap_and_market"], 0)


if __name__ == "__main__":
    unittest.main()
