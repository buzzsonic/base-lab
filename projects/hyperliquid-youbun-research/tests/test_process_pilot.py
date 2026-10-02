import unittest
from pathlib import Path


class ProcessPilotTests(unittest.TestCase):
    def test_safety_caps_and_continuity_are_gates(self):
        text = (Path(__file__).parents[1] / "scripts" / "process_pilot.py").read_text()
        for field in ("continuity_errors", "twap_endpoint_capped", "fills_safety_cap_hit", "funding_safety_cap_hit"):
            self.assertIn(field, text)
        self.assertNotIn("forward_fill", text)


if __name__ == "__main__":
    unittest.main()
