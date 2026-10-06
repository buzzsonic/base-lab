import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "forward_market_core_collect.py"
SPEC = importlib.util.spec_from_file_location("market_core", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def ctx(received=100_000, source_time=None):
    return {
        "stream": "btc_asset_ctx",
        "received_at_ms": received,
        "source_time_ms": source_time,
        "payload": {"markPx": "100", "openInterest": "10", "funding": "0.0001"},
    }


def candle(t, received, repair=None, close_offset=59_999):
    return {
        "stream": "btc_candle_1m",
        "received_at_ms": received,
        "repair_source": repair,
        "source_time_ms": t,
        "payload": {"t": t, "T": t + close_offset, "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "3"},
    }


class ForwardMarketCoreCollectorTest(unittest.TestCase):
    def run_collect(self, root, rows, run_id="r1", finished=200_000, fail=False):
        return MODULE.collect_fixture(rows, Path(root), run_id, finished, fail_before_checkpoint=fail)

    def test_asset_ctx_source_time_remains_null(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_collect(root, [ctx()], finished=110_000)
            raw = json.loads((Path(root) / "runs/r1/btc_asset_ctx.jsonl").read_text().strip())
            self.assertIsNone(raw["source_time_ms"])
            self.assertEqual(100_000, raw["received_at_ms"])

    def test_only_finalized_candle_enters_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_collect(root, [ctx(190_000), candle(120_000, 195_000)], finished=170_000)
            self.assertEqual("", (Path(root) / "canonical_candles_1m.jsonl").read_text())
            self.assertTrue((Path(root) / "runs/r1/btc_candle_1m.jsonl").exists())

    def test_restart_duplicate_has_one_canonical_candle(self):
        with tempfile.TemporaryDirectory() as root:
            row = candle(60_000, 130_000)
            self.run_collect(root, [ctx(130_000), row], finished=140_000)
            row["received_at_ms"] = 150_000
            self.run_collect(root, [ctx(150_000), row], run_id="r2", finished=160_000)
            lines = (Path(root) / "canonical_candles_1m.jsonl").read_text().splitlines()
            self.assertEqual(1, len(lines))
            self.assertEqual(150_000, json.loads(lines[0])["received_at_ms"])

    def test_gap_is_unresolved_and_repair_source_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [ctx(300_000), candle(60_000, 130_000), candle(180_000, 250_000, "REST_CANDLE_SNAPSHOT")]
            manifest = self.run_collect(root, rows, finished=310_000)
            self.assertEqual(1, manifest["unresolved_candle_gaps"])
            canonical = [json.loads(x) for x in (Path(root) / "canonical_candles_1m.jsonl").read_text().splitlines()]
            self.assertEqual("REST_CANDLE_SNAPSHOT", canonical[1]["repair_source"])
            gaps = json.loads((Path(root) / "runs/r1/gap_manifest.json").read_text())
            self.assertIn("RESOLVED_REST", {item["status"] for item in gaps})

    def test_stale_asset_ctx_is_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.run_collect(root, [ctx(1_000)], finished=122_001)
            self.assertTrue(manifest["asset_ctx_stale"])
            gaps = json.loads((Path(root) / "runs/r1/gap_manifest.json").read_text())
            self.assertEqual("STALE_INTERVAL", gaps[-1]["status"])

    def test_optional_trade_error_does_not_fail_core(self):
        with tempfile.TemporaryDirectory() as root:
            bad_trade = {"stream": "btc_trades", "received_at_ms": 2_000, "payload": "bad"}
            manifest = self.run_collect(root, [ctx(2_000), bad_trade], finished=3_000)
            self.assertEqual("PASS_WITH_OPTIONAL_ERRORS", manifest["status"])
            self.assertEqual(1, len(manifest["optional_errors"]))
            self.assertEqual("r1", json.loads((Path(root) / "state.json").read_text())["last_successful_run_id"])

    def test_core_error_or_injected_failure_does_not_advance_checkpoint(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_collect(root, [ctx(1_000)], finished=2_000)
            with self.assertRaises(ValueError):
                self.run_collect(root, [{"stream": "btc_asset_ctx", "received_at_ms": 3_000, "payload": {}}], "r2", 4_000)
            state = json.loads((Path(root) / "state.json").read_text())
            self.assertEqual("r1", state["last_successful_run_id"])
            with self.assertRaises(RuntimeError):
                self.run_collect(root, [ctx(5_000), candle(60_000, 130_000)], "r3", 140_000, fail=True)
            state = json.loads((Path(root) / "state.json").read_text())
            self.assertEqual("r1", state["last_successful_run_id"])
            self.assertTrue((Path(root) / "runs/r3/manifest.json").exists())
            self.assertEqual("", (Path(root) / "canonical_candles_1m.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()
