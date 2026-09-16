import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from src.config import load_settings
from src.detect import build_report, fetch_volume_baselines
from src.collector import alert_decision
from src.health import collection_health
from src.metrics import nearest_prior, pct_change
from src.notify import format_digest, format_state_change_digest
from src.state import load_state, save_state

NOW=1789568296407

def asset(**kw):
    row=dict(coin='TEST',mark_px=100,prev_day_px=100,day_ntl_vlm=10_000_000,funding_hourly=.001,open_interest_coin=100_000,open_interest_usd=10_000_000)
    row.update(kw);return row

def state(hours=12):
    return dict(coins=['TEST'],oi_coin={'TEST':100_000},oi_usd={'TEST':10_000_000},observed_at_ms=NOW-hours*3_600_000)

class PrecisionTests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ',{'DRY_RUN':'true'},clear=True):self.s=load_settings()
    def report(self,row=None,prev=None):
        return build_report([row or asset()],['TEST'],{'TEST':10_000_000},prev or state(),self.s,NOW)
    def test_funding_only(self):
        r=self.report();self.assertEqual(r['total_fired'],0);self.assertEqual(r['funding_only_count'],1)
    def test_price_only_usd_oi_increase(self):
        self.assertEqual(self.report(asset(mark_px=150,open_interest_usd=15_000_000))['total_fired'],0)
    def test_quantity_expansion_contraction(self):
        for qty in (130_000,70_000):
            r=self.report(asset(open_interest_coin=qty));self.assertEqual(r['total_fired'],1);self.assertAlmostEqual(abs(r['alerts'][0]['oi_change_pct']),30)
    def test_legacy_state(self):
        prev=state();del prev['oi_coin'];r=self.report(prev=prev)
        self.assertEqual(r['missing_oi_count'],1);self.assertEqual(r['total_fired'],0)
    def test_stale_future_state(self):
        for hours in (31,-1,0):
            r=self.report(asset(open_interest_coin=200_000),state(hours));self.assertIsNone(r['comparison_hours']);self.assertEqual(r['total_fired'],0)
    def test_hl_liquidity(self):
        r=self.report(asset(day_ntl_vlm=100,open_interest_coin=200_000));self.assertEqual(r['liquidity_excluded'],1);self.assertEqual(r['total_fired'],0)
    def test_volume_price_conjunction(self):
        r=self.report(asset(mark_px=110,day_ntl_vlm=30_000_000));self.assertEqual(r['total_fired'],1);self.assertEqual(r['alerts'][0]['score'],1)
    def test_missing_display(self):
        msg=format_digest(self.report(),datetime.now(timezone.utc));self.assertIn('未判定',msg);self.assertIn('状態不明',msg);self.assertLessEqual(len(msg),2000);self.assertNotIn('$$',msg)
    def test_health_complete_hour_boundary(self):
        hour=30*3_600_000;now=hour+30*60_000
        s={'last_run_ms':hour,'history':{'X':[{'observed_at_ms':6*3_600_000+1},{'observed_at_ms':hour}]}}
        h=collection_health(s,now,self.s);self.assertEqual(h['covered_hours'],1);self.assertEqual(h['status'],'delayed')
    def test_missing_high_score_blocked(self):
        self.assertEqual(alert_decision({'anomaly_score':100,'core_data_completeness_pct':100},asset(),5,self.s)[0],'insufficient')
    def test_short_gate(self):
        f=dict(price_change_5m_pct=3,price_change_15m_pct=4,oi_qty_change_5m_pct=6,oi_qty_change_15m_pct=8,core_data_completeness_pct=100,anomaly_score=80)
        self.assertEqual(alert_decision(f,asset(),5,self.s)[0],'fired');self.assertEqual(alert_decision(f,asset(),60,self.s)[0],'insufficient')
        self.assertEqual(alert_decision(f,asset(),-1,self.s)[0],'insufficient')
        f['oi_qty_change_15m_pct']=0;self.assertEqual(alert_decision(f,asset(),5,self.s)[0],'not_fired')
    def notification(self,facts,prev):
        f=dict(anomaly_score=80,data_completeness_pct=90,high_low={})
        row=dict(symbol='TEST',features=f,decision='fired',observed_facts=facts,event_id='x',observed_at_utc='now',missing_fields=[])
        return format_state_change_digest([row],prev,NOW,self.s)
    def test_cooldown_changed_text(self):
        prev={'TEST':{'notified_at_ms':NOW-5*60_000,'band':8,'facts':['高値から-2.11%']}}
        self.assertEqual(self.notification(['高値から-2.12%'],prev),(None,{}))
    def test_hidden_block_not_acknowledged(self):
        self.assertEqual(self.notification(['長い事実'*600],{}),(None,{}))
    def test_future_nonfinite(self):
        self.assertIsNone(nearest_prior([{'observed_at_ms':NOW+1}],NOW,5,10)[0]);self.assertIsNone(pct_change(math.nan,10));self.assertIsNone(pct_change(10,math.inf))
    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';dt=datetime.now(timezone.utc)
            save_state(['TEST'],{'TEST':100},dt,Mock(),p,oi_coin={'TEST':3.125})
            loaded=load_state(Mock(),p);self.assertEqual(loaded['oi_coin']['TEST'],3.125);self.assertEqual(loaded['observed_at_ms'],int(dt.timestamp()*1000))
    def test_baseline_completed_tail(self):
        day=(int(datetime.now().timestamp()*1000)//86_400_000)*86_400_000
        client=Mock();client.candle_snapshot.return_value=[{'t':day-i*86_400_000,'v':'100','c':'10'} for i in (1,2,3)]
        with patch('src.detect.time.sleep'):result=fetch_volume_baselines(client,['TEST'],7,Mock())
        self.assertEqual(result,{'TEST':1000})

    def test_main_dry_run_integration(self):
        from src import main
        with patch.object(main, 'load_settings', return_value=self.s), \
             patch.object(main, 'HyperliquidClient'), \
             patch.object(main, 'build_watchlist', return_value=([asset(mark_px=110,day_ntl_vlm=30_000_000)],['TEST'])), \
             patch.object(main, 'fetch_volume_baselines', return_value={'TEST':10_000_000}), \
             patch.object(main, 'load_state', return_value=None), \
             patch.object(main, 'load_collector_state', return_value={}), \
             patch.object(main, 'send_discord_message') as sender, \
             patch.object(main, 'save_state') as save:
            self.assertEqual(main.run(),0)
            self.assertTrue(sender.call_args.kwargs['dry_run'])
            msg=sender.call_args.kwargs['message']
            self.assertIn('状態不明',msg);self.assertIn('**TEST**',msg);self.assertNotIn('$$',msg)
            self.assertEqual(save.call_args.kwargs['oi_coin'],{'TEST':100_000})

if __name__=='__main__':unittest.main()
