from decimal import Decimal
import unittest

from src.reconstruct import attribute_funding, continuity_errors, quality_summary, reconstruct_episodes


def fill(time, start, side, size, px, pnl="0", fee="0.1", direction=""):
    return {"time": time, "coin": "BTC", "startPosition": str(start), "side": side,
            "sz": str(size), "px": str(px), "closedPnl": str(pnl), "fee": str(fee), "dir": direction}


class ReconstructTest(unittest.TestCase):
    def test_add_partial_and_close(self):
        rows = [fill(1, 0, "B", 1, 100), fill(2, 1, "B", 1, 90),
                fill(3, 2, "A", 0.5, 110, pnl=5), fill(4, 1.5, "A", 1.5, 120, pnl=37.5)]
        episode = reconstruct_episodes("0x1", rows)[0]
        self.assertTrue(episode.closed)
        self.assertEqual(episode.number_of_adds, 1)
        self.assertEqual(episode.number_of_partial_exits, 1)
        self.assertEqual(episode.average_entry, Decimal("95"))
        self.assertEqual(episode.average_exit, Decimal("117.5"))
        self.assertEqual(episode.entry_qty, episode.exit_qty)
        self.assertEqual(quality_summary([episode])["quantity_mismatches"], 0)

    def test_flip_splits_episode(self):
        rows = [fill(1, 0, "B", 1, 100), fill(2, 1, "A", 2, 90, pnl=-10, fee="0.2")]
        episodes = reconstruct_episodes("0x1", rows)
        self.assertEqual(len(episodes), 2)
        self.assertTrue(episodes[0].closed)
        self.assertEqual(episodes[0].exit_qty, Decimal("1"))
        self.assertEqual(episodes[0].entry_qty, episodes[0].exit_qty)
        self.assertFalse(episodes[1].closed)
        self.assertEqual(episodes[1].direction, "SHORT")
        self.assertEqual(episodes[1].entry_qty, Decimal("1"))

    def test_left_censored(self):
        episode = reconstruct_episodes("0x1", [fill(1, 2, "A", 2, 100, pnl=10)])[0]
        self.assertTrue(episode.left_censored)
        self.assertTrue(episode.closed)

    def test_funding_is_attributed_by_coin_and_episode_window(self):
        episode = reconstruct_episodes("0x1", [fill(100, 0, "B", 1, 100), fill(300, 1, "A", 1, 110, pnl=10)])[0]
        attribute_funding([episode], [
            {"time": 50, "delta": {"coin": "BTC", "usdc": "99"}},
            {"time": 200, "delta": {"coin": "BTC", "usdc": "-1.25"}},
            {"time": 200, "delta": {"coin": "ETH", "usdc": "50"}},
        ], 999)
        self.assertEqual(episode.funding, Decimal("-1.25"))
        self.assertEqual(episode.net_pnl, Decimal("8.55"))

    def test_continuity_gap_is_detected(self):
        rows = [fill(1, 0, "B", 1, 100), fill(2, 2, "A", 1, 110)]
        self.assertEqual(continuity_errors(rows), 1)


if __name__ == "__main__":
    unittest.main()
