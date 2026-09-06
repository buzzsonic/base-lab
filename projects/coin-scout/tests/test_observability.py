import tempfile
import unittest
from pathlib import Path

from types import SimpleNamespace

from src.metrics import anomaly_score, high_low_from_snapshots, nearest_prior, pct_change, robust_funding_anomaly, trade_imbalance
from src.notify import format_state_change_digest
from src.collector import _features
from src.observation_store import append_unique_gzip, build_outcomes, event_id


class ObservabilityTests(unittest.TestCase):
    def test_nearest_prior_uses_actual_time_and_tolerance(self):
        now=1_000_000
        row={"observed_at_ms":now-5*60_000+30_000,"price":100}
        found,error=nearest_prior([row],now,5,1)
        self.assertEqual(found,row);self.assertAlmostEqual(error,.5)
        found,_=nearest_prior([row],now,5,.25);self.assertIsNone(found)

    def test_pct_change_missing_is_not_zero(self):
        self.assertIsNone(pct_change(10,None));self.assertAlmostEqual(pct_change(11,10),10)

    def test_funding_reference_needs_24_past_samples(self):
        self.assertIsNone(robust_funding_anomaly(.01,[.001]*23)["robust_z"])
        values=[.001+i*.00001 for i in range(24)]
        self.assertIsNotNone(robust_funding_anomaly(.01,values)["robust_z"])

    def test_trade_coverage_and_side_definition(self):
        end=1_000_000;start=end-300_000
        trades=[{"time":start-1,"side":"B","sz":"2","px":"10"},{"time":start+1,"side":"A","sz":"1","px":"10"},{"time":start+2,"side":"B","sz":"3","px":"10"}]
        result=trade_imbalance(trades,start,end)
        self.assertTrue(result["coverage_complete"]);self.assertEqual(result["buy_taker_notional_usd"],30);self.assertEqual(result["sell_taker_notional_usd"],10)
        self.assertFalse(trade_imbalance(trades[1:],start,end)["coverage_complete"])

    def test_anomaly_missing_does_not_become_zero_component(self):
        score,components=anomaly_score({"price_change_5m_pct":5})
        self.assertEqual(score,100);self.assertEqual(components,["price"])

    def test_event_id_deduplicates_same_bucket(self):
        self.assertEqual(event_id("hl","BTC",300_001,"v"),event_id("hl","BTC",599_999,"v"))

    def test_gzip_append_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.jsonl.gz";rows=[{"event_id":"a"}]
            self.assertEqual(append_unique_gzip(path,rows,"event_id"),1)
            self.assertEqual(append_unique_gzip(path,rows,"event_id"),0)

    def test_outcomes_use_observed_path_and_mark_gaps(self):
        base={"event_id":"a","observed_at_ms":0,"price":100}
        end={"event_id":"b","observed_at_ms":300_000,"price":110}
        rows=build_outcomes({"BTC":[base,end]},300_000,1)
        five=next(row for row in rows if row["horizon_minutes"]==5)
        self.assertEqual(five["status"],"observed");self.assertAlmostEqual(five["endpoint_return_pct"],10)
        self.assertAlmostEqual(five["max_rise_pct"],10);self.assertAlmostEqual(five["max_fall_pct"],0)

    def test_high_low_uses_observed_snapshot_path(self):
        rows=[{"observed_at_ms":0,"price":100},{"observed_at_ms":300_000,"price":110}]
        result=high_low_from_snapshots(rows,105,600_000)
        self.assertAlmostEqual(result["from_high_pct"],(105/110-1)*100)
        self.assertEqual(result["path_samples"],3)

    def test_state_change_message_is_observation_not_direction_score(self):
        features={"anomaly_score":80.0,"data_completeness_pct":75.0,"price_change_5m_pct":1.0,"price_change_15m_pct":2.0,"price_change_1h_pct":3.0,"price_change_24h_pct":4.0,"oi_qty_change_5m_pct":1.0,"oi_qty_change_15m_pct":2.0,"oi_qty_change_1h_pct":3.0,"funding_robust_z":None,"funding_reference_samples":2,"trade_imbalance_5m":{"coverage_complete":False},"high_low":{"from_high_pct":-1.0,"from_low_pct":2.0}}
        row={"symbol":"TEST","observed_at_utc":"2026-01-01T00:00:00+00:00","event_id":"x","decision":"fired","observed_facts":["価格上昇＋数量OI増加"],"features":features,"missing_fields":["Funding過去分布"],"freshness_seconds":None}
        settings=SimpleNamespace(state_alert_cooldown_minutes=60,state_alert_top_n=3)
        message,_=format_state_change_digest([row],{},1000,settings)
        self.assertIn("異常度順",message);self.assertNotIn("ロング優勢",message);self.assertNotIn("ショート捕まり",message)

    def test_feature_windows_use_quantity_oi(self):
        now=3_600_000
        history=[{"observed_at_ms":now-5*60_000,"price":100,"open_interest_coin":1000},{"observed_at_ms":now-15*60_000,"price":90,"open_interest_coin":900},{"observed_at_ms":0,"price":80,"open_interest_coin":800}]
        asset={"mark_px":110,"prev_day_px":100,"open_interest_coin":1100,"funding_hourly":.0001,"funding_raw":.0001,"funding_interval_hours":1.0}
        settings=SimpleNamespace(comparison_tolerance_minutes=1,funding_reference_days=14)
        features,missing=_features(asset,history,[],[],now,settings,"not_sampled_rate_limit_control")
        self.assertAlmostEqual(features["oi_qty_change_5m_pct"],10)
        self.assertAlmostEqual(features["price_change_15m_pct"],(110/90-1)*100)
        self.assertIn("約定方向ローテーション対象外",missing)


if __name__=="__main__":unittest.main()
