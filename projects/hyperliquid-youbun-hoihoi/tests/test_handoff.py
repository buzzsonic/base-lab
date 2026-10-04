import copy
import json
import unittest
from pathlib import Path

from hoihoi.handoff import validate_handoff


CONTRACT = Path(__file__).parents[1] / "contracts" / "btc-research-sample-v0.1"


class HandoffContractTests(unittest.TestCase):
    def example(self) -> dict:
        return json.loads((CONTRACT / "example_handoff.json").read_text(encoding="utf-8"))

    def test_example_is_valid_and_contract_json_parses(self):
        json.loads((CONTRACT / "selection_config.json").read_text(encoding="utf-8"))
        json.loads((CONTRACT / "handoff_schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_handoff(self.example()), [])

    def test_outcome_fields_are_rejected(self):
        payload = self.example()
        payload["wallets"][0]["net_pnl_usd"] = "1.0"
        payload["wallets"][0]["post_entry_return_5m"] = 0.01
        self.assertIn(
            "outcome fields are forbidden: net_pnl_usd,post_entry_return_5m",
            validate_handoff(payload),
        )

    def test_quality_and_activity_gates_fail_closed(self):
        payload = self.example()
        wallet = payload["wallets"][0]
        wallet["quality"]["continuity_error_count"] = 1
        wallet["btc_activity"]["fill_count"] = 19
        errors = validate_handoff(payload)
        self.assertTrue(any("continuity_error_count" in item for item in errors))
        self.assertTrue(any("fill_count" in item for item in errors))

    def test_missing_profile_is_not_silently_false(self):
        payload = self.example()
        profile = payload["wallets"][0]["behavior_profile"]["high_price_chase_candidate"]
        profile.update(status="FALSE", evidence_episodes=0)
        self.assertTrue(any("requires at least 3 evidence episodes" in item for item in validate_handoff(payload)))
        missing = copy.deepcopy(payload)
        del missing["wallets"][0]["behavior_profile"]["high_price_chase_candidate"]
        self.assertTrue(any("profile names" in item for item in validate_handoff(missing)))


if __name__ == "__main__":
    unittest.main()
