from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hoihoi.classify import classify_wallet, depletion_status
from hoihoi.discovery import leaderboard_candidates, merge_sources, normalize_wallet, trade_stream_candidates
from hoihoi.pipeline import small_alt_universe, stratified_select
from hoihoi.notify import build_message


CONFIG = {
    "schema_version": 1, "observation_days": 7,
    "activity": {"lookback_days": 30, "min_perp_fills": 3},
    "classification": {"small_median_notional": 250, "large_median_notional": 10000,
        "high_frequency_fills_30d": 5, "low_frequency_fills_30d": 2, "high_leverage": 8,
        "low_leverage": 2, "bot_fills_per_active_day": 4, "bot_median_interval_seconds": 60,
        "mm_maker_ratio": .8, "farm_max_median_notional": 50, "farm_min_symbols": 3,
        "major_ratio": .7, "small_alt_notional_cutoff": 1e6},
    "depletion": {"near_fraction": .5, "rapid_fraction": .7, "withdrawal_match_tolerance": .25}
}


def fill(t, coin="BTC", side="B", crossed=True, px="100", sz="1"):
    return {"time": t, "coin": coin, "side": side, "crossed": crossed, "px": px, "sz": sz}


class DiscoveryTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_wallet("0x" + "A" * 40), "0x" + "a" * 40)
        self.assertIsNone(normalize_wallet("0x123"))

    def test_public_trade_extraction(self):
        a, b = "0x" + "1" * 40, "0x" + "2" * 40
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "public.jsonl"
            wire = json.dumps({"channel": "trades", "data": [{"users": [a, b]}]})
            path.write_text(json.dumps({"channel": "trades", "wire": wire}) + "\n")
            rows = trade_stream_candidates([path], 10)
        self.assertEqual({r["wallet"] for r in rows}, {a, b})
        self.assertTrue(all("event_freq=" in r["source_detail"] for r in rows))

    def test_merge_deduplicates_and_preserves_provenance(self):
        w = "0x" + "1" * 40
        rows = merge_sources([[{"wallet": w, "source": "a", "source_detail": "x"}],
                              [{"wallet": w, "source": "b", "source_detail": "y"}]], 2)
        self.assertEqual(len(rows), 1)
        self.assertIn("a+b", rows[0]["source"])

    def test_leaderboard_not_pnl_order(self):
        rows = []
        for i in range(32):
            rows.append({"ethAddress": "0x" + f"{i:040x}", "accountValue": str(10 ** (i % 4 + 2)),
                         "windowPerformances": [["month", {"vlm": str(10 ** (i % 4 + 4)), "pnl": str(32-i)}]]})
        selected = leaderboard_candidates({"leaderboardRows": rows}, 16)
        self.assertEqual(len(selected), 16)
        self.assertGreaterEqual(len({r["source_detail"] for r in selected}), 4)
        self.assertGreaterEqual(len({r["leaderboard_rank_band"] for r in selected}), 2)


class ClassificationTests(unittest.TestCase):
    def test_inactive_requires_minimum_perp_activity(self):
        now = datetime.now(timezone.utc)
        row = classify_wallet("0x" + "1" * 40, [fill(int(now.timestamp()*1000))], {}, {}, now,
                              {"source": "x", "source_detail": "y"}, CONFIG)
        self.assertEqual(row["status"], "INACTIVE")

    def test_bot_mm_flags_are_non_destructive(self):
        now = datetime.now(timezone.utc)
        t = int(now.timestamp() * 1000)
        fills = [fill(t + i * 1000, side="B" if i % 2 else "A", crossed=False) for i in range(6)]
        row = classify_wallet("0x" + "1" * 40, fills, {}, {}, now,
                              {"source": "x", "source_detail": "y"}, CONFIG)
        self.assertTrue(row["bot_suspected"])
        self.assertTrue(row["mm_suspected"])
        self.assertEqual(row["status"], "OBSERVING")

    def test_spot_only_is_inactive(self):
        now = datetime.now(timezone.utc); t = int(now.timestamp() * 1000)
        row = classify_wallet("0x" + "1" * 40, [fill(t+i, coin="@1") for i in range(5)], {}, {}, now,
                              {"source": "x", "source_detail": "y"}, CONFIG)
        self.assertEqual(row["perp_trade_count_30d"], 0)
        self.assertEqual(row["status"], "INACTIVE")

    def test_funding_hedge_suspicion(self):
        now = datetime.now(timezone.utc); t = int(now.timestamp() * 1000)
        state = {"assetPositions": [{"position": {"coin": "ETH", "szi": "-10", "positionValue": "1000",
                  "leverage": {"value": 2}}}], "marginSummary": {"accountValue": "1000"}}
        spot = {"balances": [{"coin": "ETH", "total": "9.5"}]}
        row = classify_wallet("0x" + "1" * 40, [fill(t+i, coin="ETH") for i in range(3)], state, spot, now,
                              {"source": "x", "source_detail": "y"}, CONFIG)
        self.assertTrue(row["funding_arbitrage_suspected"])

    def test_depletion_and_withdrawal_are_separate(self):
        self.assertEqual(depletion_status({"equity": 100}, {"equity": 25}, [], CONFIG)[0], "RAPID_DEPLETION")
        ledger = [{"delta": {"type": "withdraw", "amount": "75"}}]
        self.assertEqual(depletion_status({"equity": 100}, {"equity": 25}, ledger, CONFIG)[0], "WITHDRAWAL_SUSPECTED")

    def test_small_alt_profile_uses_market_universe(self):
        now = datetime.now(timezone.utc); t = int(now.timestamp() * 1000)
        row = classify_wallet("0x" + "1" * 40, [fill(t+i, coin="TINY") for i in range(3)], {}, {}, now,
                              {"source": "x", "source_detail": "y"}, CONFIG, {"TINY"})
        self.assertEqual(row["symbol_profile"], "small_alt_core")


class StratificationTests(unittest.TestCase):
    def row(self, i, freq, size, symbol, source):
        return {"wallet": "0x" + f"{i:040x}", "frequency_class": freq, "size_class": size,
                "symbol_profile": symbol, "activity_time_band": "jst_00_05" if i % 2 else "jst_12_17",
                "active_days_band": "1_3" if i % 3 else "11_plus", "leaderboard_rank_band": "not_ranked",
                "discovery_source": source, "status": "OBSERVING", "data_complete": True}

    def test_stratified_select_covers_minority_bands(self):
        rows = [self.row(i, "high", "medium", "btc_eth_core", "public_trade_stream") for i in range(20)]
        rows += [self.row(21, "low", "small", "small_alt_core", "official_leaderboard")]
        rows += [self.row(22, "medium", "large", "alt_core", "official_leaderboard")]
        selected = stratified_select(rows, 6)
        self.assertIn("low", {r["frequency_class"] for r in selected})
        self.assertIn("small_alt_core", {r["symbol_profile"] for r in selected})
        self.assertIn("large", {r["size_class"] for r in selected})

    def test_small_alt_universe_uses_day_volume(self):
        meta = [{"universe": [{"name": "BTC"}, {"name": "TINY"}, {"name": "BIGALT"}]},
                [{"dayNtlVlm": "10"}, {"dayNtlVlm": "100"}, {"dayNtlVlm": "2000000"}]]
        self.assertEqual(small_alt_universe(meta, 1_000_000), {"TINY"})


class NotificationTests(unittest.TestCase):
    def test_message_is_hoihoi_specific(self):
        message = build_message("success", "Issue #8", "13 tests", "branch@sha", "collector")
        self.assertIn("🪤 養分ホイホイ｜Codex作業完了", message)
        self.assertNotIn("養分くん研究", message)
        self.assertIn("branch@sha", message)

    def test_warning_includes_note(self):
        message = build_message("warning", "Issue #8", "13 tests", "branch@sha", "collector", "1,000件はHOLD")
        self.assertIn("COMPLETED WITH NOTES", message)
        self.assertIn("1,000件はHOLD", message)


if __name__ == "__main__":
    unittest.main()
