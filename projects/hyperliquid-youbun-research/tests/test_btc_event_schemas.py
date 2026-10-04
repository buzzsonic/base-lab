import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design" / "btc-event-study"


class BtcEventSchemasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event = (DESIGN / "event_schema.md").read_text(encoding="utf-8")
        cls.outcome = (DESIGN / "outcome_schema.md").read_text(encoding="utf-8")

    def test_event_contract_has_required_crowd_and_market_fields(self):
        required = {
            "active_youbun_wallets",
            "new_long_wallets",
            "new_short_wallets",
            "long_notional_usd",
            "short_notional_usd",
            "long_short_imbalance",
            "entry_price_concentration_25bps",
            "averaging_down_wallets",
            "pyramiding_wallets",
            "realized_loss_exit_wallets",
            "leverage_median",
            "liquidation_distance_bps_median",
            "btc_oi_change_pct",
            "opposite_large_flow_notional",
            "feature_ready",
        }
        for field in required:
            self.assertIn(field, self.event)

    def test_outcomes_are_separate_and_cover_all_horizons(self):
        self.assertIn("別file・別namespace", self.outcome)
        self.assertIn("`5, 15, 30, 60`", self.outcome)
        for field in (
            "future_return",
            "mfe_up",
            "mae_down",
            "moved_against_crowd",
            "opposite_large_flow_occurred",
            "panic_exit_candidate_wallets",
            "event_chain_status",
        ):
            self.assertIn(field, self.outcome)

    def test_missingness_and_leakage_rules_are_explicit(self):
        for document in (self.event, self.outcome):
            self.assertIn("UNAVAILABLE", document)
            self.assertIn("NULL", document)
        self.assertIn("event tableへ以下を保存してはならない", self.event)
        self.assertIn("post-event outcomeは常に`cutoff_ms`より後", self.event)
        self.assertIn("outcome値をevent threshold", self.outcome)

    def test_handoff_boundary_is_versioned(self):
        self.assertIn("hoihoi-btc-handoff-v0.1", self.event)
        self.assertIn("sample_version", self.event)
        self.assertIn("wallet_source_sha256", self.event)


if __name__ == "__main__":
    unittest.main()
