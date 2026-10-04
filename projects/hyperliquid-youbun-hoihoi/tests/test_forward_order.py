import unittest
from decimal import Decimal

from hoihoi.forward_order import canonical_first_seen, envelope_rows, unique_position_chain


def row(tid, start, side, size, time=1000):
    return {"tid": tid, "time": time, "startPosition": start, "side": side, "sz": size}


class ForwardOrderTests(unittest.TestCase):
    def test_envelope_preserves_api_tie_order(self):
        raw = [row(30, "0", "B", "1"), row(10, "1", "B", "1"), row(20, "2", "A", "2")]
        output = envelope_rows("fills", "0xABC", raw, "run", 0)
        self.assertEqual([item["payload"]["tid"] for item in output], [30, 10, 20])
        self.assertEqual([item["source_sequence"] for item in output], [0, 1, 2])

    def test_overlap_dedup_keeps_first_seen_order(self):
        first = envelope_rows("fills", "0xabc", [row(2, "0", "B", "1"), row(1, "1", "A", "1")], "a", 0)
        overlap = envelope_rows("fills", "0xabc", [row(1, "1", "A", "1"), row(3, "0", "B", "2", 2000)], "b", 0)
        self.assertEqual([item["payload"]["tid"] for item in canonical_first_seen(first + overlap)], [2, 1, 3])

    def test_twap_and_regular_rows_merge_by_unique_position_chain(self):
        fills = envelope_rows("fills", "0xabc", [row(1, "0", "B", "1")], "a", 0)
        twap_payload = {"fill": row(2, "1", "B", "1")}
        twap = envelope_rows("twap", "0xabc", [twap_payload], "a", 0)
        close = envelope_rows("fills", "0xabc", [row(3, "2", "A", "2")], "a", 1)
        chain = unique_position_chain(twap + close + fills, expected_before=Decimal("0"))
        self.assertEqual([item["dedup_key"] for item in chain], ["1", "2", "3"])

    def test_ambiguous_chain_fails_closed(self):
        rows = envelope_rows("fills", "0xabc", [row(1, "0", "B", "1"), row(2, "0", "B", "1")], "a", 0)
        self.assertIsNone(unique_position_chain(rows))


if __name__ == "__main__":
    unittest.main()
