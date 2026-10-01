from decimal import Decimal
import unittest

from scripts.review_episodes import RawEpisode, choose_sample, compare, key_for, split_quantities


class ReviewEpisodesTest(unittest.TestCase):
    def test_flip_quantity_is_split(self):
        closing, opening = split_quantities(Decimal("3"), Decimal("-2"), Decimal("5"))
        self.assertEqual(closing, Decimal("3"))
        self.assertEqual(opening, Decimal("2"))

    def test_builder_fee_is_contained_in_fee(self):
        raw = RawEpisode(
            wallet="0x0",
            coin="BTC",
            direction="LONG",
            first_entry_time=1,
            last_exit_time=2,
            entry_qty=Decimal("1"),
            exit_qty=Decimal("1"),
            entry_notional=Decimal("100"),
            exit_notional=Decimal("110"),
            realized_pnl=Decimal("10"),
            fees=Decimal("1"),
            builder_fee=Decimal("0.2"),
            closed=True,
        )
        reconstructed = {
            "first_entry_time": "1", "last_exit_time": "2", "direction": "LONG",
            "entry_qty": "1", "exit_qty": "1", "average_entry": "100", "average_exit": "110",
            "number_of_adds": "0", "number_of_partial_exits": "0", "realized_pnl": "10",
            "fees": "1", "funding": "0", "closed": "True", "left_censored": "False",
        }
        status, reasons, _ = compare(raw, reconstructed)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])

    def test_sample_selection_covers_every_wallet(self):
        episodes = []
        strata = {}
        for index in range(10):
            episode = RawEpisode(
                wallet=f"wallet-{index}", coin="BTC", direction="LONG", first_entry_time=index,
                last_exit_time=index + 1, entry_qty=Decimal("1"), exit_qty=Decimal("1"), closed=True,
            )
            episodes.append(episode)
            strata[key_for(episode)] = {
                "win" if index % 2 else "loss", "long", "no_adds", "no_partial",
                "no_reversal", "hold_short", "fills_few",
            }
        selected = choose_sample(episodes, strata, 10)
        self.assertEqual({episode.wallet for episode in selected}, {episode.wallet for episode in episodes})


if __name__ == "__main__":
    unittest.main()
