import time
from typing import Any

import requests


INFO_ENDPOINT = "https://api.hyperliquid.xyz/info"


class HyperliquidApiError(RuntimeError):
    pass


class HyperliquidClient:
    def __init__(
        self,
        endpoint: str = INFO_ENDPOINT,
        timeout_seconds: int = 20,
        retries: int = 4,
        request_sleep_seconds: float = 0.12,
        logger: Any | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.request_sleep_seconds = request_sleep_seconds
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "base-lab-hype-zec-order-monitor/0.1",
            }
        )

    def post_info(self, payload: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        request_type = payload.get("type", "unknown")

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.post(self.endpoint, json=payload, timeout=self.timeout_seconds)
                response.raise_for_status()
                time.sleep(self.request_sleep_seconds)
                return response.json()
            except requests.HTTPError as exc:
                last_error = exc
                wait_seconds = self._retry_wait_seconds(response=response, attempt=attempt)
                self._log_retry(request_type, attempt, wait_seconds, exc)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                wait_seconds = min(3 * attempt, 15)
                self._log_retry(request_type, attempt, wait_seconds, exc)

            if attempt < self.retries:
                time.sleep(wait_seconds)

        raise HyperliquidApiError(f"Hyperliquid API request failed: type={request_type}, error={last_error}")

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

    def spot_meta(self) -> dict[str, str]:
        data = self.post_info({"type": "spotMeta"})
        if not isinstance(data, dict):
            return {}

        token_by_index: dict[int, str] = {}
        for token in data.get("tokens", []):
            if not isinstance(token, dict):
                continue
            index = token.get("index")
            name = token.get("name")
            if isinstance(index, int) and name:
                token_by_index[index] = str(name)

        pairs: dict[str, str] = {}
        for fallback_index, pair in enumerate(data.get("universe", [])):
            if not isinstance(pair, dict):
                continue
            pair_index = pair.get("index")
            if not isinstance(pair_index, int):
                pair_index = fallback_index
            key = f"@{pair_index}"
            tokens = pair.get("tokens")
            if isinstance(tokens, list) and len(tokens) == 2:
                base = token_by_index.get(tokens[0])
                quote = token_by_index.get(tokens[1])
                if base and quote:
                    pairs[key] = f"{base}/{quote}"
                    continue
            name = pair.get("name")
            if name:
                pairs[key] = str(name)
        return pairs

    def frontend_open_orders(self, address: str) -> list[dict[str, Any]]:
        data = self.post_info({"type": "frontendOpenOrders", "user": address})
        if not isinstance(data, list):
            raise HyperliquidApiError(f"frontendOpenOrders の応答形式が不正です: address={address}")
        return [item for item in data if isinstance(item, dict)]

    def _retry_wait_seconds(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 45)
            except ValueError:
                pass
        if response.status_code == 429:
            return min(6 * attempt, 45)
        return min(2 * attempt, 15)

    def _log_retry(self, request_type: str, attempt: int, wait_seconds: float, exc: Exception) -> None:
        if self.logger is None or attempt >= self.retries:
            return
        self.logger.warning(
            f"Hyperliquid API retry: type={request_type}, attempt={attempt}/{self.retries}, "
            f"wait={wait_seconds:.1f}s, error={exc}"
        )
