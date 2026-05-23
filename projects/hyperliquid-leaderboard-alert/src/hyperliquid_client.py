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
        timeout_seconds: int = 15,
        retries: int = 3,
        logger: Any | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "base-lab-hyperliquid-leaderboard-alert/0.1",
            }
        )

    def post_info(self, payload: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        request_type = payload.get("type", "unknown")

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.post(
                    self.endpoint,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as exc:
                    raise HyperliquidApiError(
                        f"Hyperliquid API のJSON解析に失敗しました: type={request_type}"
                    ) from exc
            except requests.HTTPError as exc:
                last_error = exc
                wait_seconds = self._retry_wait_seconds(response=response, attempt=attempt)
                self._log_retry(request_type, attempt, wait_seconds, exc)
            except requests.RequestException as exc:
                last_error = exc
                wait_seconds = min(2 * attempt, 10)
                self._log_retry(request_type, attempt, wait_seconds, exc)

            if attempt < self.retries:
                time.sleep(wait_seconds)

        raise HyperliquidApiError(f"Hyperliquid API request failed: type={request_type}, error={last_error}")

    def clearinghouse_state(self, address: str) -> dict[str, Any]:
        data = self.post_info({"type": "clearinghouseState", "user": address})
        if not isinstance(data, dict):
            raise HyperliquidApiError(f"clearinghouseState の応答形式が不正です: address={address}")
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

    def _retry_wait_seconds(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 30)
            except ValueError:
                pass
        if response.status_code == 429:
            return min(5 * attempt, 30)
        return min(2 * attempt, 10)

    def _log_retry(self, request_type: str, attempt: int, wait_seconds: float, exc: Exception) -> None:
        if self.logger is None or attempt >= self.retries:
            return
        self.logger.warning(
            f"Hyperliquid API retry: type={request_type}, attempt={attempt}/{self.retries}, "
            f"wait={wait_seconds:.1f}s, error={exc}"
        )
