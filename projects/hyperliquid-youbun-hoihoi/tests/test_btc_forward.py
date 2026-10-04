import json
import tempfile
import unittest
from pathlib import Path

from hoihoi.btc_forward import collect_canary


class FakeApi:
    def __init__(self, fail_twap=False):
        self.fail_twap = fail_twap

    def get_json(self, _url, payload):
        if payload["type"] == "candleSnapshot":
            return [{"t": payload["req"]["startTime"], "T": payload["req"]["endTime"], "c": "100"}]
        if payload["type"] == "userTwapSliceFillsByTime":
            if self.fail_twap:
                raise RuntimeError("twap unavailable")
            return [{"fill": {"tid": 2, "coin": "BTC", "time": payload["startTime"], "startPosition": "1", "side": "A", "sz": "1"}}]
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


if __name__ == "__main__":
    unittest.main()
