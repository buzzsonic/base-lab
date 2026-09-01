import math
import statistics
from .config import Settings
from .models import AssetSnapshot, Detection, Metrics


def change(new: float | None, old: float | None) -> float | None:
    return None if new is None or old in (None, 0) else new / old - 1


def volume_multiplier(latest: float | None, history: list[float]) -> float | None:
    baseline = statistics.mean(history) if history else 0
    return None if latest is None or baseline <= 0 else latest / baseline


def zscore(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 6: return None
    sd = statistics.pstdev(history)
    return 0.0 if sd == 0 else (value-statistics.mean(history))/sd


def _points(snapshot: AssetSnapshot, history: list[AssetSnapshot], minutes: int):
    target = snapshot.exchanges["hyperliquid"].ts - minutes*60_000
    eligible = [x for x in history if x.exchanges.get("hyperliquid") and x.exchanges["hyperliquid"].ts <= target]
    return eligible[-1].exchanges["hyperliquid"] if eligible else None


def compute_metrics(snapshot: AssetSnapshot, history: list[AssetSnapshot], candles: list[dict], funding_history: list[float], direction: str) -> Metrics:
    now=snapshot.exchanges["hyperliquid"]
    price={}; oi={}
    for label, mins in (("5m",5),("15m",15),("1h",60),("6h",360),("24h",1440)):
        old=_points(snapshot,history,mins); price[label]=change(now.price, old.price if old else None)
        if mins>=15: oi[label]=change(now.oi_usd, old.oi_usd if old else None)
    all_volumes=[]
    for c in candles[-289:]:
        try: all_volumes.append(float(c.get("v",0))*float(c.get("c",0)))
        except AttributeError: pass
    latest=all_volumes[-1] if all_volumes else None; volumes=all_volumes[:-1]
    volume={"5m":volume_multiplier(latest,volumes),"15m":volume_multiplier(sum(all_volumes[-3:]) if len(all_volumes)>=3 else None,[sum(volumes[i:i+3]) for i in range(0,max(0,len(volumes)-3),3)]),"1h":volume_multiplier(sum(all_volumes[-12:]) if len(all_volumes)>=12 else None,[sum(volumes[i:i+12]) for i in range(0,max(0,len(volumes)-12),12)])}
    funding={name:p.funding_hourly for name,p in snapshot.exchanges.items()}
    values=[x for x in funding.values() if x is not None]
    agree=sum(1 for x in values if x<0) if direction=="short" else sum(1 for x in values if x>0)
    highs=[float(c.get("h",0)) for c in candles[-13:-1]]; lows=[float(c.get("l",0)) for c in candles[-13:-1]]
    return Metrics(price,oi,volume,funding,funding_history[-1] if funding_history else None,zscore(now.funding_hourly,funding_history),agree,len(values),bool(highs and now.price>max(highs)),bool(lows and now.price<min(lows)))


def detect(snapshot: AssetSnapshot, history: list[AssetSnapshot], candles: list[dict], funding_history: list[float], settings: Settings, direction: str) -> Detection:
    m=compute_metrics(snapshot,history,candles,funding_history,direction); price_sign=1 if direction=="short" else -1; funding_sign=-1 if direction=="short" else 1
    f=m.funding.get("hyperliquid"); oi=m.oi.get("1h"); px=m.price.get("1h"); vol=m.volume.get("5m")
    level=0
    for idx in range(4):
        f_ok=f is not None and funding_sign*f >= abs(settings.funding[idx])
        oi_period="24h" if idx==3 else "1h"; oi_value=m.oi.get(oi_period)
        oi_ok=oi_value is not None and oi_value>=settings.oi_1h[idx]
        vol_ok=vol is not None and vol>=settings.volume[idx]
        if idx==0: px_ok=px is not None and price_sign*px>=0
        elif idx==1: px_ok=px is not None and price_sign*px>=.01 and f is not None and m.funding_previous is not None and funding_sign*f > funding_sign*m.funding_previous
        elif idx==2: px_ok=px is not None and price_sign*px>=.03 and (m.breakout_up if direction=="short" else m.breakout_down) and m.agreement_count>=2
        else: px6=m.price.get("6h"); px_ok=px6 is not None and price_sign*px6>=.15
        required=3 if idx==0 else 4
        if sum((f_ok,oi_ok,vol_ok,px_ok))>=required: level=idx+1
    funding_points=min(30, int(abs(f or 0)/.0001*3)); z_points=min(10,int(abs(m.funding_zscore or 0)*2)); oi_points=min(25,int(max(0,oi or 0)/.12*25)); price_points=min(15,int(max(0,price_sign*(px or 0))/.03*15)); volume_points=min(15,int(max(0,(vol or 1)-1)/1.5*15)); agreement_points=round(10*m.agreement_count/max(1,m.agreement_total)); breakout_points=5 if (m.breakout_up if direction=="short" else m.breakout_down) else 0
    score=min(100,funding_points+z_points+oi_points+price_points+volume_points+agreement_points+breakout_points)
    reasons=[f"price 1h {px or 0:+.2%}",f"OI 1h {oi or 0:+.2%}",f"funding/h {f or 0:+.4%}",f"volume {vol or 0:.1f}x"]
    return Detection(snapshot.symbol,direction,level,score,m,reasons,["価格/OI/Funding/出来高の次段階閾値を同時確認"])
