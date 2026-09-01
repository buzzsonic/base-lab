import time
from .http import PublicClient
from .models import MarketPoint


class Bybit:
    def __init__(self): self.http = PublicClient("https://api.bybit.com")
    def markets(self) -> dict[str, MarketPoint]:
        instruments = self.http.request("GET", "/v5/market/instruments-info", params={"category":"linear", "limit":1000})["result"]["list"]
        intervals = {x["symbol"]: int(x.get("fundingInterval", 480))/60 for x in instruments if x.get("status") == "Trading" and x.get("quoteCoin") == "USDT"}
        rows = self.http.request("GET", "/v5/market/tickers", params={"category":"linear"})["result"]["list"]
        now=int(time.time()*1000); out={}
        for x in rows:
            s=x["symbol"]
            if s not in intervals: continue
            price=float(x["markPrice"]); raw_funding=x.get("fundingRate")
            funding=float(raw_funding)/intervals[s] if raw_funding not in (None,"") else None
            out[s]=MarketPoint(now, price, float(x.get("openInterest") or 0)*price, float(x.get("turnover24h") or 0), funding)
        return out
    def candles(self, symbol, count=289): return self.http.request("GET", "/v5/market/kline", params={"category":"linear", "symbol":symbol, "interval":"5", "limit":min(count,1000)})["result"]["list"]
    def funding_history(self, symbol, days): return self.http.request("GET", "/v5/market/funding/history", params={"category":"linear", "symbol":symbol, "limit":min(days*3,200)})["result"]["list"]
