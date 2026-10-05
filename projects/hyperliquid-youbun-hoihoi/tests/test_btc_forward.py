import json
import tempfile
import unittest
from pathlib import Path

from hoihoi.btc_forward import audit_canary_overlap, collect_canary, collect_canary_cohort


class FakeApi:
    def __init__(self, fail_twap=False):
        self.fail_twap = fail_twap

    def get_json(self, _url, payload):
        if payload["type"] == "candleSnapshot":
            return [{"t": payload["req"]["startTime"], "T": payload["req"]["endTime"], "c": "100"}]
        if payload["type"] == "userTwapSliceFillsByTime":
            if self.fail_twap:
                raise RuntimeError("twap unavailable")
            return [{"fill": {"tid": 2, "coin": "BTC", "time": payload["startTime"] + 1, "startPosition": "1", "side": "A", "sz": "1"}}]
        return [{"tid": 1, "coin": "BTC", "time": payload["startTime"], "startPosition": "0", "side": "B", "sz": "1"}]


class BtcForwardCanaryTests(unittest.TestCase):
    def test_invalid_wallet_is_rejected_before_api_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "20-byte hex"):
                collect_canary(FakeApi(), "not-a-wallet", Path(tmp), 2_000_000)

    def test_separate_raw_sources_and_state_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = collect_canary(FakeApi(), "0x" + "1" * 40, output, 2_000_000)
            run = output / "raw" / "date=1970-01-01" / f"run={result['run_id']}"
            self.assertTrue((run / "fills.jsonl").exists())
            self.assertTrue((run / "twap.jsonl").exists())
            self.assertTrue((run / "btc_5m.jsonl").exists())
            fill = json.loads((run / "fills.jsonl").read_text().splitlines()[0])
            self.assertEqual(fill["row_index"], 0)
            self.assertEqual(result["quality_gate"], "PASS")
            self.assertTrue(result["state_advanced"])

    def test_endpoint_failure_keeps_raw_manifest_but_not_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = collect_canary(FakeApi(fail_twap=True), "0x" + "1" * 40, output, 2_000_000)
            self.assertEqual(result["quality_gate"], "FAIL")
            self.assertFalse((output / "state" / "collector_state.json").exists())
            manifests = list(output.glob("raw/date=*/run=*/manifest.json"))
            self.assertEqual(len(manifests), 1)

    def test_wallet_is_frozen_after_first_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            collect_canary(FakeApi(), "0x" + "1" * 40, output, 2_000_000)
            with self.assertRaisesRegex(ValueError, "wallet cannot change"):
                collect_canary(FakeApi(), "0x" + "2" * 40, output, 3_200_000)

    def test_two_poll_overlap_audit_preserves_first_seen_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            wallet = "0x" + "1" * 40
            first = collect_canary(FakeApi(), wallet, output, 2_000_000)
            second = collect_canary(FakeApi(), wallet, output, 2_002_000)
            report = audit_canary_overlap(output)
            self.assertEqual(report["quality_gate"], "PASS", report)
            self.assertEqual(report["run_count"], 2)
            self.assertEqual(report["overlap_duplicates_retained_raw"], 2)
            self.assertTrue(report["first_seen_preserved"])
            self.assertEqual(report["state_last_run_id"], second["run_id"])
            self.assertNotEqual(first["run_id"], second["run_id"])

    def test_audit_fails_closed_with_only_one_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            collect_canary(FakeApi(), "0x" + "1" * 40, output, 2_000_000)
            report = audit_canary_overlap(output)
            self.assertEqual(report["quality_gate"], "FAIL")
            self.assertIn("RUN_COUNT_NOT_TWO", report["failure_reasons"])

    def test_frozen_cohort_starts_forward_only_and_stops_after_24h(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "cohort.json"
            config.write_text(json.dumps({
                "schema_version": 1, "cohort_id": "test", "window_hours": 24,
                "wallets": [{"wallet": "0x" + "1" * 40, "role": "test"}],
            }))
            output = root / "output"
            first = collect_canary_cohort(FakeApi(), config, output, 2_000_000)
            self.assertEqual(first["quality_gate"], "PASS")
            self.assertEqual(first["analysis_start_ms"], 2_000_000)
            manifest = first["wallet_results"][0]
            self.assertEqual(manifest["endpoint_results"]["fills"]["records"], 1)
            complete = collect_canary_cohort(FakeApi(), config, output, 2_000_000 + 24 * 60 * 60_000 + 1)
            self.assertEqual(complete["quality_gate"], "WINDOW_COMPLETE")

    def test_cohort_config_is_frozen_after_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "cohort.json"
            config.write_text(json.dumps({
                "schema_version": 1, "cohort_id": "test", "window_hours": 24,
                "wallets": [{"wallet": "0x" + "1" * 40, "role": "test"}],
            }))
            collect_canary_cohort(FakeApi(), config, root / "output", 2_000_000)
            config.write_text(config.read_text().replace('"role": "test"', '"role": "changed"'))
            with self.assertRaisesRegex(ValueError, "config changed"):
                collect_canary_cohort(FakeApi(), config, root / "output", 2_002_000)


if __name__ == "__main__":
    unittest.main()
