from __future__ import annotations
import argparse,csv,hashlib
from decimal import Decimal
from pathlib import Path
from scripts.review_episodes import read_csv,eligibility_reasons,anonymized_aliases,load_wallet_raw,dec
from scripts.apply_preregistered_labels import classify_add
from scripts.audit_market_coverage import write_csv

Z=Decimal('0')
def build(data,config):
 import json
 cfg=json.loads(config.read_text())['adds']; q=read_csv(data/'quality'/'account_quality.csv'); wallets=[r['wallet'].lower() for r in q if not eligibility_reasons(r)]; aliases=anonymized_aliases([r['wallet'].lower() for r in q]); out=[]
 for w in wallets:
  fills,_=load_wallet_raw(data/'raw',w); states={}; seq={}
  for original,(idx,r) in enumerate(sorted(enumerate(fills),key=lambda x:(int(x[1]['time']),x[0]))):
   coin=r['coin']; before=dec(r['startPosition']); qty=dec(r['sz']); px=dec(r['px']); after=before+(qty if r['side']=='B' else -qty)
   s=states.get(coin)
   if s is None: s={'start':int(r['time']),'avg':px,'initial':abs(after),'dir':'LONG' if after>Z else 'SHORT'}; states[coin]=s; seq[coin]=0
   if before*after>Z and abs(after)>abs(before):
    add=abs(after)-abs(before); seq[coin]+=1; kind=classify_add(s['dir'],s['avg'],px,add,abs(before),cfg); dist=(px/s['avg']-1)*(Decimal(1) if s['dir']=='LONG' else Decimal(-1)); trace=f"{r['time']}|{r.get('tid',r.get('hash',''))}|{idx}"
    out.append({'wallet_anon_id':aliases[w],'episode_trace':f"{aliases[w]}|{coin}|{s['start']}",'stable_sequence_index':seq[coin],'timestamp':r['time'],'coin':coin,'side':s['dir'],'pre_add_position_size':str(abs(before)),'pre_add_avg_entry_price':str(s['avg']),'add_price':str(px),'add_qty':str(add),'add_notional':str(add*px),'add_size_ratio_vs_existing':str(add/abs(before)),'signed_price_distance_vs_pre_add_avg':str(dist),'favorable_or_adverse':kind,'resulting_position_size':str(abs(after)),'label_v1_classification':'AVERAGING_DOWN' if kind=='adverse' else ('PROFIT_PYRAMIDING' if kind=='profit' else 'NONE'),'source_fill_trace_key':hashlib.sha256(trace.encode()).hexdigest()[:20]})
    s['avg']=(s['avg']*abs(before)+px*add)/abs(after)
   if after==Z or before*after<Z:
    states.pop(coin,None); seq.pop(coin,None)
    if before*after<Z: states[coin]={'start':int(r['time']),'avg':px,'initial':abs(after),'dir':'LONG' if after>Z else 'SHORT'}; seq[coin]=0
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rows=build(a.data,a.config);a.output.mkdir(parents=True,exist_ok=True);write_csv(a.output/'add_events.csv',rows)
 (a.output/'README.md').write_text(f"# Add evidence v1\n\nGenerated {len(rows)} outcome-free same-direction add events with stable trace keys. PnL, outcome, MFE/MAE and post-entry data are absent.\n")
 (a.output/'schema.md').write_text('# Schema\n\nEach row is one same-direction add fill in stable `(time, original server order)` sequence. `signed_price_distance_vs_pre_add_avg` is favorable-positive for both LONG and SHORT. `label_v1_classification` uses frozen v1 size and 5bp thresholds.\n')
if __name__=='__main__':main()
