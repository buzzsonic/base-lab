import logging
import time
from datetime import datetime, timezone
from .binance import Binance
from .bybit import Bybit
from .config import Settings
from .detector import detect
from .hyperliquid import Hyperliquid
from .models import AssetSnapshot
from .notifier import send, send_clear
from .state import append, decode, load, save

ALIASES={"KPEPE":"1000PEPE","KBONK":"1000BONK","KFLOKI":"1000FLOKI","KSHIB":"1000SHIB","KLUNC":"1000LUNC"}
def map_symbol(hl_symbol: str, exchange_symbols: set[str]) -> str | None:
    direct=hl_symbol+"USDT"
    if direct in exchange_symbols:return direct
    alias=ALIASES.get(hl_symbol.upper())
    return alias+"USDT" if alias and alias+"USDT" in exchange_symbols else None

def _candles(raw, exchange):
    out=[]; closed_before=(int(time.time()*1000)//300_000)*300_000
    for row in raw:
        if exchange=="hyperliquid": out.append(row)
        elif exchange=="binance": out.append({"t":row[0],"o":row[1],"h":row[2],"l":row[3],"c":row[4],"v":row[5]})
        else: out.append({"t":row[0],"o":row[1],"h":row[2],"l":row[3],"c":row[4],"v":row[5]})
    return sorted((x for x in out if int(x["t"])+300_000<=closed_before),key=lambda x:int(x["t"]))

def should_notify(previous, detection, settings, now):
    if detection.level<=0:return False
    if not previous or detection.level>int(previous.get("level",0)):return True
    elapsed=now-float(previous.get("ts",0)); delta=detection.score-int(previous.get("score",0))
    return elapsed>=settings.renotify_hours*3600 and delta>=settings.renotify_score_delta

def run():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s"); log=logging.getLogger("hl-squeeze-monitor")
    settings=Settings(); state=load(); clients={"hyperliquid":Hyperliquid(),"binance":Binance(),"bybit":Bybit()}; markets={}
    for name,client in clients.items():
        try: markets[name]=client.markets(); log.info("%s OK: %d markets",name,len(markets[name]))
        except Exception as exc: log.warning("%s ERROR: %s",name,exc); markets[name]={}
    if not markets["hyperliquid"]: raise RuntimeError("Hyperliquid universe unavailable; refusing to evaluate")
    mapped=[]
    for symbol,hp in markets["hyperliquid"].items():
        b=map_symbol(symbol,set(markets["binance"])); y=map_symbol(symbol,set(markets["bybit"]))
        if (b or y) and hp.volume_24h_usd>=settings.min_volume: mapped.append((symbol,b,y))
    if settings.max_symbols:mapped=mapped[:settings.max_symbols]
    log.info("monitoring %d Hyperliquid-listed symbols",len(mapped)); now=time.time()
    for symbol,b_symbol,y_symbol in mapped:
        exchanges={"hyperliquid":markets["hyperliquid"][symbol]}
        if b_symbol:
            exchanges["binance"]=markets["binance"][b_symbol]
            try: exchanges["binance"].oi_usd=clients["binance"].oi(b_symbol)*exchanges["binance"].price
            except Exception as exc: log.warning("%s Binance OI unavailable: %s",symbol,exc)
        if y_symbol: exchanges["bybit"]=markets["bybit"][y_symbol]
        snapshot=AssetSnapshot(symbol,exchanges); history=[decode(x) for x in state.get("history",{}).get(symbol,[])]
        try:
            if b_symbol: candles=_candles(clients["binance"].candles(b_symbol),"binance")
            elif y_symbol: candles=_candles(clients["bybit"].candles(y_symbol),"bybit")
            else: candles=_candles(clients["hyperliquid"].candles(symbol),"hyperliquid")
        except Exception as exc: log.warning("%s candles unavailable: %s",symbol,exc); candles=[]
        fh=[x.exchanges["hyperliquid"].funding_hourly for x in history if x.exchanges.get("hyperliquid") and x.exchanges["hyperliquid"].funding_hourly is not None]
        for direction in ("short","long"):
            d=detect(snapshot,history,candles,fh,settings,direction); key=f"{symbol}:{direction}"; prev=state.setdefault("alerts",{}).get(key)
            if settings.debug: log.info("%s %s level=%d score=%d %s",symbol,direction,d.level,d.score,d.reasons)
            if should_notify(prev,d,settings,now):
                if settings.debug or send(settings.webhook,d): state["alerts"][key]={"level":d.level,"score":d.score,"ts":now}
            elif d.level==0 and prev and int(prev.get("level",0))>=2:
                if settings.debug or send_clear(settings.webhook,symbol,direction): state["alerts"].pop(key,None)
        append(state,snapshot)
    state["last_run_utc"]=datetime.now(timezone.utc).isoformat(); save(state)

if __name__=="__main__": run()
