from src.config import Settings
from src.detector import change, detect, volume_multiplier
from src.main import map_symbol, should_notify
from src.models import AssetSnapshot, MarketPoint

def point(ts,price=100,oi=1000,funding=-.0001,volume=2_000_000): return MarketPoint(ts,price,oi,volume,funding)
def history(now, short=True):
    out=[]
    for i in range(289):
        ts=now-(289-i)*300_000; price=100; oi=1000
        out.append(AssetSnapshot("SKR",{"hyperliquid":point(ts,price,oi,-.0007 if short else .0007)}))
    return out
def candles(short=True):
    rows=[]
    for i in range(289):
        p=100+(i*.01 if short else -i*.01); rows.append({"t":i,"o":p,"h":p+.01,"l":p-.01,"c":p,"v":100})
    rows[-1]["v"]=300
    return rows

def test_funding_normalization_examples():
    assert -.0008/8 == -.0001
    assert -.0008/(480/60) == -.0001
def test_mapping_is_conservative():
    symbols={"BTCUSDT","1000PEPEUSDT"}
    assert map_symbol("BTC",symbols)=="BTCUSDT"
    assert map_symbol("KPEPE",symbols)=="1000PEPEUSDT"
    assert map_symbol("PEPE",symbols) is None
def test_change_and_volume():
    assert abs(change(110,100)-.1)<1e-12
    assert volume_multiplier(20,[10,10])==2
    assert change(1,0) is None
def test_short_skr_reaches_level_2_or_3():
    now=2_000_000_000_000; hist=history(now,True); snap=AssetSnapshot("SKR",{"hyperliquid":point(now,104.5,1160,-.0016),"binance":point(now,funding=-.0012),"bybit":point(now,funding=-.0011)})
    d=detect(snap,hist,candles(True),[-.0002,-.0004,-.0007],Settings(),"short")
    assert d.level>=2 and d.score>=50 and d.metrics.agreement_count==3
def test_long_squeeze_is_inverse():
    now=2_000_000_000_000; hist=history(now,False); snap=AssetSnapshot("SKR",{"hyperliquid":point(now,95.5,1160,.0016),"binance":point(now,funding=.0012),"bybit":point(now,funding=.0011)})
    d=detect(snap,hist,candles(False),[.0002,.0004,.0007],Settings(),"long")
    assert d.level>=2 and d.metrics.agreement_count==3
def test_promotion_and_duplicate_suppression():
    s=Settings(); d=type("D",(),{"level":2,"score":70})()
    assert should_notify(None,d,s,100)
    assert not should_notify({"level":2,"score":70,"ts":99},d,s,100)
    d.level=3; assert should_notify({"level":2,"score":70,"ts":99},d,s,100)
def test_missing_api_data_does_not_crash():
    now=2_000_000_000_000; snap=AssetSnapshot("X",{"hyperliquid":point(now)})
    assert detect(snap,[],[],[],Settings(),"short").level==0
