import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/youbun-hoihoi-shadow-observe.yml"


class ShadowCohortWorkflowTests(unittest.TestCase):
    def test_shadow_state_is_isolated_and_fail_closed(self):
        text = WORKFLOW.read_text()
        cohort = "outputs/cohorts/stratified-20261003"
        self.assertIn(cohort, text)
        self.assertNotIn("state=persisted/projects/hyperliquid-youbun-hoihoi/outputs/current", text)
        self.assertIn('test -f "$state/wallet_registry.parquet"', text)
        self.assertIn('test -f "$state/discovery_pool.parquet"', text)
        self.assertIn('test -f "$state/cohort_manifest.json"', text)
        self.assertIn("group: youbun-hoihoi-data", text)
        self.assertIn("push_data_branch.sh\" data 3", text)


if __name__ == "__main__":
    unittest.main()
