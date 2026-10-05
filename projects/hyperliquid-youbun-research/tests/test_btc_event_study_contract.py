import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "design" / "btc-event-study" / "field_matrix.csv"
RESEARCH_DIRECTION = ROOT / "RESEARCH_DIRECTION.md"
NEXT_TASK = ROOT / "NEXT_TASK.md"


class BtcEventStudyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with MATRIX.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_required_fields_are_unique_and_classified(self):
        keys = [(row["domain"], row["field"]) for row in self.rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            {"取得可能", "forwardなら取得可能", "取得不能"},
            {row["availability"] for row in self.rows},
        )

        required = {
            ("wallet", "fills"),
            ("wallet", "TWAP fills"),
            ("wallet", "Funding cash flow"),
            ("wallet", "current position size"),
            ("wallet", "side"),
            ("wallet", "entry price"),
            ("wallet", "configured leverage"),
            ("wallet", "margin mode"),
            ("wallet", "liquidation price"),
            ("wallet", "account equity"),
            ("wallet", "margin usage"),
            ("wallet", "effective leverage proxy"),
            ("wallet", "add/reduce/close"),
            ("wallet", "realized-loss exit"),
            ("btc", "price/OHLCV"),
            ("btc", "volume"),
            ("btc", "open interest"),
            ("btc", "OI change"),
            ("btc", "Funding rate"),
            ("btc", "volatility"),
            ("btc", "aggressive buy/sell flow"),
            ("btc", "large trade flow"),
            ("btc", "order-book imbalance"),
            ("btc", "liquidation flow"),
        }
        self.assertTrue(required.issubset(set(keys)))

    def test_every_field_has_source_grain_and_quality_rule(self):
        required_columns = {
            "domain",
            "field",
            "availability",
            "official_source",
            "raw_fields_or_derivation",
            "history_boundary",
            "proposed_grain",
            "quality_rule",
        }
        self.assertEqual(required_columns, set(self.rows[0]))
        for row in self.rows:
            for column in required_columns:
                self.assertTrue(row[column].strip(), f"{row['field']}: empty {column}")

    def test_research_order_is_real_data_pdca_before_reporting(self):
        direction = RESEARCH_DIRECTION.read_text(encoding="utf-8")
        next_task = NEXT_TASK.read_text(encoding="utf-8")
        for phrase in (
            "研究PDCA",
            "exploratory期間で仮説ごとにbacktest",
            "別期間・別sample",
            "有意義なeffect size",
            "最終レポートは研究の開始点ではなく",
        ):
            self.assertIn(phrase, direction)
        self.assertIn("実データbacktest readiness監査【次】", next_task)
        self.assertIn("validation / held-out再現性検証", next_task)

    def test_synthetic_mock_is_not_research_evidence(self):
        direction = RESEARCH_DIRECTION.read_text(encoding="utf-8")
        next_task = NEXT_TASK.read_text(encoding="utf-8")
        self.assertIn("synthetic report mockは参考UI", direction)
        self.assertIn("研究判断、採否には使わず", next_task)


if __name__ == "__main__":
    unittest.main()
