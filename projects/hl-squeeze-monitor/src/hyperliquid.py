import time
from .http import PublicClient
from .models import MarketPoint


class Hyperliquid:
    def __init__(self): self.http = PublicClient("https://api.hyperliquid.xyz")
    def _info(self, payload): return self.http.request("POST", "/info", json=payload)

    def markets(self) -> dict[str, MarketPoint]:
        meta, ctxs = self._info({"type": "metaAndAssetCtxs"})
        now = int(time.time() * 1000); out = {}
        for meta_item, ctx in zip(meta["universe"], ctxs):
            if ctx.get("isDelisted") or not ctx.get("markPx"): continue
            symbol = meta_item["name"].upper()
            price = float(ctx["markPx"]); oi_coin = float(ctx.get("openInterest", 0))
            out[symbol] = MarketPoint(now, price, oi_coin * price, float(ctx.get("dayNtlVlm", 0)), float(ctx["funding"]) if ctx.get("funding") is not None else None)
        return out

    def candles(self, symbol: str, count: int = 289):
        end = int(time.time() * 1000); start = end - count * 300_000
        return self._info({"type": "candleSnapshot", "req": {"coin": symbol, "interval": "5m", "startTime": start, "endTime": end}})

    def funding_history(self, symbol: str, days: int):
        now = int(time.time() * 1000)
        return self._info({"type": "fundingHistory", "coin": symbol, "startTime": now-days*86_400_000, "endTime": now})
