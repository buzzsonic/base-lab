import unittest
from pathlib import Path


class PilotCollectorTests(unittest.TestCase):
    def test_checkpoint_contract_is_present(self):
        text = (Path(__file__).parents[1] / "scripts" / "collect_pilot.py").read_text()
        for field in ("last_success_timestamp", "retries", "failures", "endpoint_cap_hit", "complete"):
            self.assertIn(field, text)
        self.assertNotIn("privateKey", text)
        self.assertNotIn("placeOrder", text)


if __name__ == "__main__":
    unittest.main()
