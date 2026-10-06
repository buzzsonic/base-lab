import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("market_live", ROOT / "scripts/forward_market_core_live.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ForwardMarketCoreLiveTest(unittest.TestCase):
    def test_transforms_official_channels_without_inventing_ctx_time(self):
        ctx = MODULE.transform_message({"channel": "activeAssetCtx", "data": {"coin": "BTC", "ctx": {
            "markPx": "1", "openInterest": "2", "funding": "3"}}}, 100)
        self.assertIsNone(ctx[0]["source_time_ms"])
        candle = MODULE.transform_message({"channel": "candle", "data": {
            "s": "BTC", "i": "1m", "t": 60, "T": 119, "o": "1", "h": "1", "l": "1", "c": "1", "v": "1"}}, 120)
        self.assertEqual(60, candle[0]["source_time_ms"])

    def test_trade_filter_and_tid_are_preserved(self):
        rows = MODULE.transform_message({"channel": "trades", "data": [
            {"coin": "BTC", "time": 10, "tid": 7}, {"coin": "ETH", "time": 10, "tid": 8}]}, 11)
        self.assertEqual(1, len(rows))
        self.assertEqual(7, rows[0]["payload"]["tid"])

    @patch("urllib.request.urlopen")
    def test_rest_repair_is_explicit(self, urlopen):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        response = Response()
        import io
        response.read = io.BytesIO(b'[{"t":60,"T":119,"o":"1","h":"1","l":"1","c":"1","v":"1"}]').read
        urlopen.return_value = response
        rows = MODULE.fetch_candle_repairs(60, 120)
        self.assertEqual("REST_CANDLE_SNAPSHOT", rows[0]["repair_source"])


if __name__ == "__main__": unittest.main()
