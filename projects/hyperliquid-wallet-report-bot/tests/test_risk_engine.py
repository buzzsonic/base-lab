import tempfile
import unittest
from pathlib import Path

from src.models import AccountSnapshot, Fill
from src.risk_engine import equity_stats, reconstruct_cycles
from src.storage import WalletStore
from src.dashboard import build_dashboard


def fill(t, coin, side, start, size, px, pnl=0, tid=None):
    return Fill(coin, "", px, size, pnl, 1, t, False,
                {"side": side, "startPosition": str(start), "tid": tid or t, "oid": t, "hash": "0x1"})


class RiskEngineTests(unittest.TestCase):
    def test_partial_add_close_and_full_close_are_one_cycle(self):
        rows = [fill(1000,"UNI","B",0,10,9), fill(2000,"UNI","B",10,5,8),
                fill(3000,"UNI","A",15,4,10,4), fill(4000,"UNI","A",11,11,11,22)]
        cycles = reconstruct_cycles(rows)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0]["number_of_adds"], 1)
        self.assertEqual(cycles[0]["number_of_partial_closes"], 1)
        self.assertEqual(cycles[0]["realized_pnl"], 26)

    def test_long_to_short_flip(self):
        cycles = reconstruct_cycles([fill(1000,"UNI","B",0,10,9), fill(2000,"UNI","A",10,15,8,-10)])
        self.assertEqual([(c["direction"], c["closed_at"]) for c in cycles], [("LONG",2000),("SHORT",None)])

    def test_short_to_long_flip(self):
        cycles = reconstruct_cycles([fill(1000,"UNI","A",0,10,9), fill(2000,"UNI","B",-10,15,10,-10)])
        self.assertEqual([(c["direction"], c["closed_at"]) for c in cycles], [("SHORT",2000),("LONG",None)])

    def test_duplicate_tid_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "risk.db"; row = fill(1000,"UNI","B",0,1,9,tid="42")
            store = WalletStore(path); self.assertEqual(store.save_fills([row,row]), 1); store.close()
            store = WalletStore(path); self.assertEqual(len(store.fills_between(0,2000)), 1); store.close()

    def test_peak_drawdown_300_550_920_250_is_72_8_percent(self):
        snap = AccountSnapshot(4000,250,250,0,0,[],[])
        eq = equity_stats(snap,[{"account_value":v} for v in (300,550,920,250)],0,[])
        self.assertEqual(round(eq["drawdown_pct"],1),72.8)

    def test_dashboard_contains_bybit_style_views_and_real_trade(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "risk.db"; output = Path(d) / "dashboard" / "index.html"
            rows = [fill(1000,"UNI","B",0,10,9), fill(2000,"UNI","A",10,10,10,10)]
            store = WalletStore(path); store.save_fills(rows); store.replace_trades(reconstruct_cycles(rows))
            store.save_market_contexts(1000, ({"universe":[{"name":"UNI"}]}, [{"dayNtlVlm":"2500000"}]))
            build_dashboard(store, output, 2000); store.close()
            text = output.read_text(encoding="utf-8")
            self.assertIn("勝敗分析", text)
            self.assertIn("Entry時24h出来高別", text)
            self.assertIn('"coin":"UNI"', text)
            self.assertIn('"volume24h":2500000.0', text)


if __name__ == "__main__": unittest.main()
