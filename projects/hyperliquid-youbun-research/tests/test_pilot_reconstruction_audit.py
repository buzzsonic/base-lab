import unittest
from pathlib import Path


class PilotReconstructionAuditTests(unittest.TestCase):
    def test_retention_and_reconstruction_failures_are_hard_exclusions(self):
        text = (Path(__file__).parents[1] / "scripts" / "audit_pilot_reconstruction.py").read_text()
        for reason in ("refetch_coverage_loss", "twap_retention_gap", "unrecoverable_fill_gap",
                       "quantity_mismatch", "no_completed_episode"):
            self.assertIn(reason, text)
        self.assertNotIn("forward_fill", text)


if __name__ == "__main__":
    unittest.main()
