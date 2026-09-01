import json
from urllib.request import Request, urlopen

LABELS={1:"👀 監視 第1段階",2:"👀👀 強監視 第2段階",3:"🫵 SQUEEZE候補 第3段階",4:"🔥 EXTREME"}
def _pct(v): return "N/A" if v is None else f"{v:+.3%}"
def build_embed(d):
    m=d.metrics; agreement="WEAK" if m.agreement_count<=1 else "MEDIUM" if m.agreement_count==2 else "STRONG"
    return {"title":f"{LABELS[d.level]} [{d.symbol}]", "description":f"{d.direction.upper()} SQUEEZE候補\nSqueeze Score: **{d.score}/100**", "color":0xff9500 if d.direction=="short" else 0x5865f2,"fields":[{"name":"価格","value":"\n".join(f"{k} {_pct(v)}" for k,v in m.price.items()),"inline":True},{"name":"OI","value":"\n".join(f"{k} {_pct(v)}" for k,v in m.oi.items()),"inline":True},{"name":"Funding / hour","value":"\n".join(f"{k}: {_pct(v)}" for k,v in m.funding.items()),"inline":False},{"name":"Funding一致度","value":f"{m.agreement_count}/{m.agreement_total} {agreement}","inline":True},{"name":"出来高倍率","value":f"5m {m.volume.get('5m') or 0:.1f}x","inline":True}],"footer":{"text":"監視通知であり売買推奨ではありません"}}
def send(webhook,d):
    if not webhook: return False
    req=Request(webhook,data=json.dumps({"embeds":[build_embed(d)]}).encode(),headers={"Content-Type":"application/json"}); urlopen(req,timeout=10).read(); return True
def send_clear(webhook,symbol,direction):
    if not webhook:return False
    req=Request(webhook,data=json.dumps({"content":f"✅ {symbol} {direction.upper()} SQUEEZE WATCH解除"}).encode(),headers={"Content-Type":"application/json"});urlopen(req,timeout=10).read();return True
