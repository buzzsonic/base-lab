import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "deploy" / "vps"


class VpsRuntimeTests(unittest.TestCase):
    def test_runtime_contract_is_v3_read_only_and_fail_safe(self):
        runner = (DEPLOY / "run_collector.sh").read_text()
        compose = (DEPLOY / "docker-compose.yml").read_text()
        service = (DEPLOY / "youbun-collector.service").read_text()
        timer = (DEPLOY / "youbun-collector.timer").read_text()
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "youbun-v3-runtime-ci.yml").read_text()
        self.assertIn("forward-data-v3", runner)
        self.assertIn("--collector-version forward-v3", runner)
        self.assertIn("flock -n", runner)
        self.assertIn("merge --ff-only", runner)
        self.assertIn("timeout --signal=TERM", runner)
        self.assertIn("collector timeout; checkpoint unchanged", runner)
        self.assertIn("/etc/youbun-collector.env", compose)
        self.assertIn("TimeoutStartSec=20min", service)
        self.assertIn("OnCalendar=*:0/5", timer)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("docker build", workflow)
        for forbidden in ("privateKey", "placeOrder", "/exchange"):
            self.assertNotIn(forbidden, runner)

    def test_status_emits_required_structured_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({
                "run_id": "r1", "requested_wallets": 1,
                "endpoint_results": [{"endpoint": "fills"}],
                "failures": 0, "cap_hits": 0, "retention_risks": 0,
            }))
            output = subprocess.check_output([
                "python3", str(DEPLOY / "status.py"), "--manifest", str(manifest),
                "--started-at", "2026-10-04T00:00:00Z",
                "--finished-at", "2026-10-04T00:00:05Z", "--exit-code", "0",
            ], text=True)
            row = json.loads(output)
            self.assertEqual(row["duration_seconds"], 5)
            required = {"run_id", "started_at", "finished_at", "duration_seconds",
                        "wallet_count", "endpoint_count", "failures", "cap_hits",
                        "retention_risks", "exit_code"}
            self.assertTrue(required.issubset(row))


if __name__ == "__main__":
    unittest.main()
