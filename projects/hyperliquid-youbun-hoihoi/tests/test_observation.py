import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hoihoi.history import collect_fills
from hoihoi.observation import merge_observation

class Api:
    def __init__(self, fills):
        self.fills = fills
        self.calls = []
    def get_json(self, url, payload):
        self.calls.append(payload)
        return [f for f in self.fills if payload['startTime'] <= f['time'] <= payload['endTime']][:2000]

class HistoryTests(unittest.TestCase):
    def test_split_increment_dedupe_and_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fills.json'
            api = Api([{'time': i, 'tid': i} for i in range(3000)])
            result = collect_fills(api, 'wallet', path, 0, 3000)
            self.assertTrue(result['complete'])
            self.assertEqual(len(result['fills']),3000)
            api.fills.append({'time':3001,'tid':3001})
            api.calls=[]
            result=collect_fills(api,'wallet',path,0,3002)
            self.assertEqual(api.calls[0]['startTime'],3000)
            self.assertEqual(len(result['fills']),3001)
    def test_same_ms_saturation_and_budget_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            api=Api([{'time':1,'tid':i} for i in range(2000)])
            result=collect_fills(api,'w',Path(tmp)/'a.json',1,1)
            self.assertFalse(result['complete'])
            result=collect_fills(api,'w',Path(tmp)/'b.json',0,5,max_requests=1)
            self.assertFalse(result['complete'])
    def test_failure_does_not_advance_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.json';api=Api([])
            collect_fills(api,'w',path,0,1);before=path.read_text()
            api.get_json=lambda *args: (_ for _ in ()).throw(RuntimeError('network'))
            with self.assertRaises(RuntimeError):collect_fills(api,'w',path,0,2)
            self.assertEqual(path.read_text(),before)
    def test_10000_retention_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=collect_fills(Api([{'time':i,'tid':i} for i in range(10000)]),'w',Path(tmp)/'a.json',0,10001)
            self.assertFalse(result['complete'])
            self.assertTrue(result['retention_risk'])

class ObservationTests(unittest.TestCase):
    def test_seven_days_and_same_day_rerun(self):
        now=datetime(2026,10,1,tzinfo=timezone.utc)
        row={'first_seen':now.isoformat(),'status':'OBSERVING','data_complete':True}
        config={'observation_days':7,'min_observation_days':7}
        prior=None
        for day in range(7):
            prior=merge_observation(row,prior,now+timedelta(days=day),config)
        self.assertEqual(prior['status'],'OBSERVING')
        active=merge_observation(row,prior,now+timedelta(days=7),config)
        self.assertEqual(active['status'],'ACTIVE')
        again=merge_observation(row,active,now+timedelta(days=7),config)
        self.assertEqual(again['successful_observation_days'],8)
        row['bot_suspected']=True
        self.assertEqual(merge_observation(row,active,now+timedelta(days=8),config)['status'],'EXCLUDED')
    def test_old_first_seen_is_not_observation_evidence(self):
        now=datetime(2026,10,8,tzinfo=timezone.utc)
        row={'first_seen':(now-timedelta(days=7)).isoformat(),'status':'OBSERVING','data_complete':True}
        self.assertEqual(merge_observation(row,None,now,{'observation_days':7})['status'],'OBSERVING')

class PipelineTests(unittest.TestCase):
    def test_observe_roundtrip_does_not_reset_first_seen(self):
        from argparse import Namespace
        from unittest.mock import patch
        from hoihoi.pipeline import run_poc, ROOT
        from hoihoi.storage import read_parquet, write_parquet
        class Public:
            def __init__(self,*args):pass
            def market_contexts(self,*args):return [{'universe':[{'name':'BTC'}]},[{'dayNtlVlm':'20000000'}]]
            def get_json(self,url,payload):
                return [{'time':payload['endTime']-i*100000,'tid':payload['endTime']+i,'coin':'BTC','side':'B','px':'100','sz':'1','crossed':True} for i in range(3)]
            def clearinghouse_state(self,*args):return {}
            def spot_state(self,*args):return {}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            write_parquet(out/'discovery_pool.parquet', [{'wallet':'0x'+'2'*40,'first_seen':'2026-09-30T00:00:00+00:00','discovery_source':'official_leaderboard','discovery_detail':'unselected'}])
            write_parquet(out/'wallet_registry.parquet',[{'wallet':'0x'+'1'*40,'first_seen':'2026-10-01T00:00:00+00:00','discovery_source':'public_trade_stream','discovery_detail':'test','poc_selected':True}])
            args=Namespace(config=ROOT/'config.json',output=out,as_of='2026-10-02T00:00:00+00:00',limit=None,public_stream=None,refresh=True,command='observe')
            with patch('hoihoi.pipeline.PublicApi',Public):
                manifest=run_poc(args)
                first=read_parquet(out/'wallet_registry.parquet')[0]
                args.as_of='2026-10-03T00:00:00+00:00'
                run_poc(args)
            second=read_parquet(out/'wallet_registry.parquet')[0]
            self.assertEqual(manifest['active_sample_wallets'],0)
            self.assertEqual(first['first_seen'],second['first_seen'])
            self.assertEqual(second['successful_observation_days'],2)
            self.assertEqual(second['status'],'OBSERVING')
            self.assertTrue(second['poc_selected'])
            pool=read_parquet(out/'discovery_pool.parquet')
            self.assertEqual({r['wallet'] for r in pool},{'0x'+'1'*40,'0x'+'2'*40})
            unselected=next(r for r in pool if r['wallet']=='0x'+'2'*40)
            self.assertEqual(unselected['first_seen'],'2026-09-30T00:00:00+00:00')
            self.assertEqual(unselected['discovery_detail'],'unselected')


class StorageTests(unittest.TestCase):
    def test_new_observation_fields_survive_old_row_first(self):
        from hoihoi.storage import read_parquet, write_parquet
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pool.parquet'
            write_parquet(path,[{'wallet':'old'}, {'wallet':'new','observation_dates':['2026-10-02'],'data_complete':True}])
            rows=read_parquet(path)
            self.assertEqual(rows[1]['observation_dates'],['2026-10-02'])
            self.assertTrue(rows[1]['data_complete'])
            self.assertIsNone(rows[0]['observation_dates'])
