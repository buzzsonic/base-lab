import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hoihoi.quality_gate import build_comparison, summarize_cohort
from hoihoi.storage import write_parquet


def row(wallet: str, *, days: int = 7, status: str = "ACTIVE", complete: bool = True) -> dict:
    return {
        "wallet": wallet,
        "status": status,
        "data_complete": complete,
        "eligible_after": "2026-10-08T00:00:00+00:00",
        "successful_observation_days": days,
        "symbol_profile": "small_alt_core",
        "bot_suspected": False,
        "mm_suspected": False,
        "farm_suspected": False,
        "arbitrage_suspected": False,
        "funding_arbitrage_suspected": False,
    }


class QualityGateTests(unittest.TestCase):
    def seed(self, path: Path, rows: list[dict], sample: list[dict]) -> None:
        write_parquet(path / "wallet_registry.parquet", rows)
        pool = list(rows)
        pool.extend({"wallet": f"pool-extra-{index}"} for index in range(200 - len(pool)))
        write_parquet(path / "discovery_pool.parquet", pool)
        write_parquet(path / "research_sample.parquet", sample)

    def test_ready_requires_active_sample_identity_and_all_candidate_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            rows = [row(f"0x{i:040x}") for i in range(100)]
            self.seed(path, rows, [{"wallet": item["wallet"]} for item in rows])
            report = summarize_cohort(path, datetime(2026, 10, 9, tzinfo=timezone.utc))
            self.assertEqual(report["structural_gate"], "PASS")
            self.assertEqual(report["promotion_gate"], "READY_FOR_HUMAN_REVIEW")
            rows[0]["successful_observation_days"] = 6
            self.seed(path, rows, [{"wallet": item["wallet"]} for item in rows])
            self.assertEqual(
                summarize_cohort(path, datetime(2026, 10, 9, tzinfo=timezone.utc))["promotion_gate"],
                "HOLD",
            )

    def test_incomplete_and_flagged_wallets_are_reported_but_not_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            current, shadow = Path(tmp) / "current", Path(tmp) / "shadow"
            current_rows = [row(f"0x{i:040x}") for i in range(100)]
            shadow_rows = [dict(item) for item in current_rows]
            shadow_rows[0].update(status="OBSERVING", data_complete=False)
            shadow_rows[1].update(status="EXCLUDED", bot_suspected=True)
            self.seed(current, current_rows, [{"wallet": item["wallet"]} for item in current_rows])
            self.seed(shadow, shadow_rows, [{"wallet": item["wallet"]} for item in shadow_rows[2:]])
            report = build_comparison(current, shadow, datetime(2026, 10, 9, tzinfo=timezone.utc))
            self.assertEqual(report["shadow"]["incomplete_histories"], 1)
            self.assertEqual(report["shadow"]["bot_suspected"], 1)
            self.assertEqual(report["shadow"]["valid_candidates"], 98)
            self.assertEqual(report["shadow"]["promotion_gate"], "READY_FOR_HUMAN_REVIEW")
            self.assertEqual(report["replacement_gate"], "READY_FOR_HUMAN_REVIEW")

    def test_duplicate_or_sample_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            rows = [row(f"0x{i:040x}") for i in range(99)] + [row("0x" + "0" * 40)]
            self.seed(path, rows, [])
            report = summarize_cohort(path, datetime(2026, 10, 9, tzinfo=timezone.utc))
            self.assertEqual(report["duplicates"], 1)
            self.assertEqual(report["structural_gate"], "FAIL")
            self.assertEqual(report["promotion_gate"], "HOLD")

    def test_weekly_workflow_uses_jst_date_and_dedicated_queue(self):
        workflow = (
            Path(__file__).parents[3] / ".github" / "workflows" / "youbun-hoihoi-weekly.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("group: youbun-hoihoi-weekly", workflow)
        self.assertIn("TZ=Asia/Tokyo date +%Y-%m-%d", workflow)
        self.assertNotIn("date -u +%Y-%m-%d", workflow)


if __name__ == "__main__":
    unittest.main()
