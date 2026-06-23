import json
import time
import urllib.error
import urllib.request
from typing import Any


INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"


class HyperliquidApiError(RuntimeError):
    pass


class HyperliquidClient:
    def __init__(self, endpoint: str = INFO_ENDPOINT, timeout_seconds: int = 20, retries: int = 3, logger: Any | None = None) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.logger = logger

    def post_info(self, payload: dict[str, Any]) -> Any:
        request_type = payload.get("type", "unknown")
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload, separators=(",", ":")).encode(),
                    method="POST",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": "AICompanyHyperliquidWalletReportBot/0.1",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode())
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    wait_seconds = min(2 * attempt, 10)
                    if self.logger:
                        self.logger.warning(
                            f"Hyperliquid API retry: type={request_type}, attempt={attempt}/{self.retries}, "
                            f"wait={wait_seconds}s, error={exc}"
                        )
                    time.sleep(wait_seconds)

        raise HyperliquidApiError(f"Hyperliquid API request failed: type={request_type}, error={last_error}")

    def clearinghouse_state(self, address: str) -> dict[str, Any]:
        data = self.post_info({"type": "clearinghouseState", "user": address})
        if not isinstance(data, dict):
            raise HyperliquidApiError("clearinghouseState の応答形式が不正です。")
        return data

    def all_mids(self) -> dict[str, float]:
        data = self.post_info({"type": "allMids"})
        if not isinstance(data, dict):
            raise HyperliquidApiError("allMids の応答形式が不正です。")
        mids: dict[str, float] = {}
        for coin, value in data.items():
            try:
                mids[str(coin)] = float(value)
            except (TypeError, ValueError):
                continue
        return mids

    def frontend_open_orders(self, address: str) -> list[dict[str, Any]]:
        data = self.post_info({"type": "frontendOpenOrders", "user": address})
        if not isinstance(data, list):
            raise HyperliquidApiError("frontendOpenOrders の応答形式が不正です。")
        return data

    def user_fills(self, address: str) -> list[dict[str, Any]]:
        data = self.post_info({"type": "userFills", "user": address, "aggregateByTime": True})
        if not isinstance(data, list):
            raise HyperliquidApiError("userFills の応答形式が不正です。")
        return data

    def user_fills_by_time(self, address: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        data = self.post_info(
            {
                "type": "userFillsByTime",
                "user": address,
                "startTime": start_ms,
                "endTime": end_ms,
                "aggregateByTime": True,
            }
        )
        if not isinstance(data, list):
            raise HyperliquidApiError("userFillsByTime の応答形式が不正です。")
        return data

    def fetch_wallet_snapshot(self, address: str) -> dict[str, Any]:
        state = self.clearinghouse_state(address)
        time.sleep(0.15)
        mids = self.all_mids()
        time.sleep(0.15)
        orders = self.frontend_open_orders(address)
        time.sleep(0.15)
        fills = self.user_fills(address)
        return {"state": state, "mids": mids, "orders": orders, "fills": fills}

