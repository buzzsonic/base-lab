import time
from .http import PublicClient
from .models import MarketPoint


class Binance:
    def __init__(self): self.http = PublicClient("https://fapi.binance.com")
    def markets(self) -> dict[str, MarketPoint]:
        info = self.http.request("GET", "/fapi/v1/exchangeInfo")
        allowed = {x["symbol"] for x in info["symbols"] if x["contractType"] == "PERPETUAL" and x["status"] == "TRADING" and x["quoteAsset"] == "USDT"}
        tickers = {x["symbol"]: x for x in self.http.request("GET", "/fapi/v1/ticker/24hr")}
        premiums = {x["symbol"]: x for x in self.http.request("GET", "/fapi/v1/premiumIndex")}
        now = int(time.time()*1000); out = {}
        for s in allowed & tickers.keys() & premiums.keys():
            t, p = tickers[s], premiums[s]; price = float(p["markPrice"])
            out[s] = MarketPoint(now, price, 0, float(t["quoteVolume"]), float(p["lastFundingRate"])/8)
        return out
    def oi(self, symbol): return float(self.http.request("GET", "/fapi/v1/openInterest", params={"symbol": symbol})["openInterest"])
    def candles(self, symbol, count=289): return self.http.request("GET", "/fapi/v1/klines", params={"symbol": symbol, "interval": "5m", "limit": min(count, 1500)})
    def funding_history(self, symbol, days): return self.http.request("GET", "/fapi/v1/fundingRate", params={"symbol": symbol, "limit": min(days*3, 1000)})
