from __future__ import annotations

import json
import random
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


INFO_URL = "https://api.hyperliquid.xyz/info"
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


class PublicApi:
    """Small read-only client with a shared request budget and raw cache."""

    def __init__(self, cache_dir: Path, min_interval: float = 1.25, retries: int = 6):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.retries = retries
        self.last_request = 0.0

    def _wait(self) -> None:
        remaining = self.min_interval - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)

    def get_json(self, url: str, payload: dict | None = None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json", "User-Agent": "youbun-hoihoi/0.1"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._wait()
            try:
                with urlopen(Request(url, data=body, headers=headers), timeout=45) as response:
                    value = json.load(response)
                self.last_request = time.monotonic()
                return value
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                self.last_request = time.monotonic()
                last_error = exc
                if attempt + 1 < self.retries:
                    retry_after = getattr(exc, "headers", {}).get("Retry-After") if hasattr(exc, "headers") else None
                    delay = float(retry_after) if retry_after else min(5 * 2**attempt, 90)
                    time.sleep(delay + random.random())
        raise RuntimeError(f"public API request failed: {payload or url}: {last_error}")

    def cached(self, key: str, url: str, payload: dict | None = None, refresh: bool = False):
        path = self.cache_dir / f"{key}.json"
        if path.exists() and not refresh:
            return json.loads(path.read_text())
        value = self.get_json(url, payload)
        path.write_text(json.dumps(value, ensure_ascii=False))
        return value

    def leaderboard(self, refresh: bool = False) -> dict:
        return self.cached("leaderboard", LEADERBOARD_URL, refresh=refresh)

    def user_fills(self, wallet: str, refresh: bool = False) -> list[dict]:
        return self.cached(f"fills_{wallet.lower()}", INFO_URL,
                           {"type": "userFills", "user": wallet, "aggregateByTime": False}, refresh)

    def clearinghouse_state(self, wallet: str, refresh: bool = False) -> dict:
        return self.cached(f"perp_state_{wallet.lower()}", INFO_URL,
                           {"type": "clearinghouseState", "user": wallet}, refresh)

    def spot_state(self, wallet: str, refresh: bool = False) -> dict:
        return self.cached(f"spot_state_{wallet.lower()}", INFO_URL,
                           {"type": "spotClearinghouseState", "user": wallet}, refresh)

    def market_contexts(self, refresh: bool = False) -> list:
        return self.cached("meta_and_asset_ctxs", INFO_URL, {"type": "metaAndAssetCtxs"}, refresh)

    def ledger_updates(self, wallet: str, start_ms: int, end_ms: int) -> list[dict]:
        return self.get_json(INFO_URL, {"type": "userNonFundingLedgerUpdates", "user": wallet,
                                       "startTime": start_ms, "endTime": end_ms})
