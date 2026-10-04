import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.forward_collect import collect, fetch_pages


def write_sample(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["wallet", "anon_wallet_id"])
        writer.writeheader()
        for index in range(100):
            writer.writerow({"wallet": f"0x{index:040x}", "anon_wallet_id": f"P{index:03d}"})


class ForwardCollectorTests(unittest.TestCase):
    def test_collect_writes_envelopes_and_preserves_fixed_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sample.csv"
            output = root / "forward-data"
            write_sample(sample)

            def fake_get_json(_url, payload):
                if payload["type"] == "userFillsByTime":
                    return [{"time": 1_000_000, "tid": 1, "coin": "BTC"}]
                if payload["type"] == "userTwapSliceFillsByTime":
                    return [{"fill": {"time": 1_000_000, "tid": 2, "coin": "ETH"}, "twapId": 7}]
                return [{"time": 1_000_000, "coin": "BTC", "usdc": "-0.1"}]

            with patch("scripts.forward_collect.get_json", side_effect=fake_get_json):
                first = collect(sample, output, 1_000_000, 20 * 60_000, 0, max_wallets=1)
                second = collect(sample, output, 2_200_000, 20 * 60_000, 0, max_wallets=1)

            self.assertEqual(first["failures"], 0)
            self.assertEqual(first["retention_risks"], 0)
            self.assertEqual(first["records"], 3)
            self.assertEqual(second["requests"], 2)  # Funding is hourly.
            state = json.loads((output / "state" / "collector_state.json").read_text())
            self.assertEqual(state["analysis_start_ms"], 1_000_000)
            first_run = output / "raw" / "date=1970-01-01" / "run=19700101T001640Z"
            envelope = json.loads((first_run / "twap.jsonl").read_text().splitlines()[0])
            self.assertEqual(envelope["source_endpoint"], "userTwapSliceFillsByTime")
            self.assertEqual(envelope["source_time"], 1_000_000)
            self.assertEqual(envelope["dedup_key"], "2")

    def test_inclusive_boundary_pagination_deduplicates(self):
        boundary = 2_000
        first_page = [{"time": boundary, "tid": index} for index in range(2_000)]
        second_page = [first_page[-1], {"time": boundary + 1, "tid": 2_000}]
        calls = []

        def fake_get_json(_url, payload):
            calls.append(payload)
            return first_page if len(calls) == 1 else second_page

        with patch("scripts.forward_collect.get_json", side_effect=fake_get_json):
            rows, requests, cap_hit = fetch_pages("fills", "0x0", 1_000, 3_000, 0)

        self.assertEqual(len(rows), 2_001)
        self.assertEqual(requests, 2)
        self.assertFalse(cap_hit)
        self.assertEqual(calls[1]["startTime"], boundary)

    def test_response_size_controls_rate_limit_delay(self):
        page = [{"time": 2_000, "tid": index} for index in range(2_000)]
        with patch("scripts.forward_collect.get_json", side_effect=[page, []]), \
             patch("scripts.forward_collect.time.sleep") as sleep:
            fetch_pages("fills", "0x0", 1_000, 3_000, 2.2)
        self.assertEqual(sleep.call_args_list[0].args[0], 12.0)
        self.assertEqual(sleep.call_args_list[1].args[0], 2.2)

    def test_manifest_change_is_rejected_after_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sample.csv"
            output = root / "forward-data"
            write_sample(sample)
            with patch("scripts.forward_collect.get_json", return_value=[]):
                collect(sample, output, 1_000_000, 20 * 60_000, 0, max_wallets=1)
            sample.write_text(sample.read_text().replace("P000", "CHANGED", 1))
            with self.assertRaisesRegex(ValueError, "sampling manifest changed"):
                collect(sample, output, 2_200_000, 20 * 60_000, 0, max_wallets=1)

    def test_retention_risk_is_a_manifest_quality_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sample.csv"
            output = root / "forward-data-v2"
            write_sample(sample)
            fills = [{"time": 1_000_000, "tid": index} for index in range(10_000)]

            def fake_fetch(endpoint, *_args, **_kwargs):
                return (fills, 5, False) if endpoint == "fills" else ([], 1, False)

            with patch("scripts.forward_collect.fetch_pages", side_effect=fake_fetch):
                manifest = collect(sample, output, 1_000_000, 20 * 60_000, 0, max_wallets=1)

            self.assertEqual(manifest["retention_risks"], 1)
            self.assertEqual(manifest["endpoint_results"][0]["retention_risk"], True)
            self.assertFalse((output / "state" / "collector_state.json").exists())

    def test_failed_run_does_not_advance_existing_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "sample.csv"
            output = root / "forward-data-v3"
            write_sample(sample)
            with patch("scripts.forward_collect.get_json", return_value=[]):
                collect(sample, output, 1_000_000, 20 * 60_000, 0, max_wallets=1,
                        collector_version="forward-v3")
            before = (output / "state" / "collector_state.json").read_bytes()
            with patch("scripts.forward_collect.fetch_pages", side_effect=RuntimeError("endpoint failed")):
                manifest = collect(sample, output, 2_200_000, 20 * 60_000, 0, max_wallets=1,
                                   collector_version="forward-v3")
            self.assertGreater(manifest["failures"], 0)
            self.assertEqual((output / "state" / "collector_state.json").read_bytes(), before)
            self.assertEqual(json.loads(before)["collector_version"], "forward-v3")

    def test_workflow_is_read_only_and_uses_data_branch(self):
        workflow = Path(__file__).parents[3] / ".github" / "workflows" / "youbun-research-forward-collector.yml"
        text = workflow.read_text()
        self.assertIn("ref: data", text)
        self.assertIn("forward-data-v2", text)
        self.assertIn('cron: "*/5 * * * *"', text)
        self.assertIn("Enforce collector quality flags", text)
        self.assertIn("PYTHONPATH=projects/hyperliquid-youbun-research", text)
        self.assertIn("python -m unittest discover", text)
        for forbidden in ("privateKey", "placeOrder", "/exchange"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
