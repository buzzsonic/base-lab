import json
from pathlib import Path
from .models import AssetSnapshot, MarketPoint

PATH=Path(".state/state.json")
def load(path=PATH):
    try:
        data=json.loads(path.read_text())
        return data if isinstance(data,dict) else {"history":{},"alerts":{}}
    except (OSError,json.JSONDecodeError): return {"history":{},"alerts":{}}
def save(data,path=PATH):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))); tmp.replace(path)
def encode(snapshot): return {"symbol":snapshot.symbol,"exchanges":{k:vars(v) for k,v in snapshot.exchanges.items()}}
def decode(raw): return AssetSnapshot(raw["symbol"],{k:MarketPoint(**v) for k,v in raw["exchanges"].items()})
def append(data,snapshot,limit=300): data.setdefault("history",{}).setdefault(snapshot.symbol,[]).append(encode(snapshot)); data["history"][snapshot.symbol]=data["history"][snapshot.symbol][-limit:]
