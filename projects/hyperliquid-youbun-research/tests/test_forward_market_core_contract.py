import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design" / "forward-market-core-v1"


class ForwardMarketCoreContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((DESIGN / "contract.json").read_text(encoding="utf-8"))
        cls.collector_doc = (DESIGN / "collector_contract.md").read_text(encoding="utf-8")
        cls.gate_doc = (DESIGN / "quality_gate.md").read_text(encoding="utf-8")

    def test_design_is_separate_and_not_live(self):
        self.assertEqual("market-core-v1", self.contract["collector_version"])
        self.assertEqual("forward-market-core-v1/", self.contract["storage_namespace"])
        self.assertTrue(self.contract["existing_wallet_collector_unchanged"])
        self.assertFalse(self.contract["live_collection_started"])
        self.assertIn("forward-data-v3/", self.collector_doc)
        self.assertIn("live起動は別タスク", self.gate_doc)

    def test_core_and_optional_streams_are_minimal(self):
        self.assertEqual(
            {"btc_asset_ctx", "btc_candle_1m", "collector_health"},
            set(self.contract["core_streams"]),
        )
        self.assertEqual({"btc_trades"}, set(self.contract["optional_streams"]))
        self.assertEqual(
            {"wallet_state", "bbo", "l2", "liquidation_event"},
            set(self.contract["deferred"]),
        )

    def test_source_time_and_missingness_are_not_fabricated(self):
        asset = self.contract["core_streams"]["btc_asset_ctx"]
        self.assertTrue(asset["source_time_nullable"])
        self.assertEqual("NONE", asset["automatic_backfill"])
        self.assertIn("source_time_ms", self.contract["raw_envelope"]["nullable"])
        for forbidden in ("forward_fill", "zero_fill_missing", "synthetic_asset_ctx"):
            self.assertIn(forbidden, self.contract["forbidden"])

    def test_one_minute_candle_repair_is_bounded_and_auditable(self):
        candle = self.contract["core_streams"]["btc_candle_1m"]
        self.assertEqual("1m", candle["subscription"]["interval"])
        self.assertEqual(60_000, candle["expected_step_ms"])
        self.assertTrue(candle["canonical_finalized_only"])
        self.assertEqual(5_000, candle["repair"]["maximum_recent_candles"])
        self.assertEqual("REST_CANDLE_SNAPSHOT", candle["repair"]["repair_source"])
        self.assertEqual(
            {"OPEN", "RESOLVED_REST", "UNRESOLVED"},
            set(self.contract["gap_statuses"]),
        )

    def test_quality_gate_blocks_research_on_core_gaps(self):
        for phrase in (
            "期待1,440本の100%",
            "unresolved candle gap: 0",
            "asset ctx fresh coverage: 99.5%以上",
            "PHASE 4B",
            "H08は`UNAVAILABLE`",
        ):
            self.assertIn(phrase, self.gate_doc)


if __name__ == "__main__":
    unittest.main()
