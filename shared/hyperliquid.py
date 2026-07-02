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
        request_sleep_seconds: float = 0.0,
        user_agent: str = "base-lab-hyperliquid/0.1",
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
                "User-Agent": user_agent,
            }
        )

    def post_info(self, payload: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        request_type = payload.get("type", "unknown")

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.post(self.endpoint, json=payload, timeout=self.timeout_seconds)
                response.raise_for_status()
                if self.request_sleep_seconds > 0:
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

    def meta_and_asset_ctxs(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data = self.post_info({"type": "metaAndAssetCtxs"})
        if not isinstance(data, list) or len(data) != 2:
            raise HyperliquidApiError("metaAndAssetCtxs の応答形式が不正です。")
        meta, asset_ctxs = data
        if not isinstance(meta, dict) or not isinstance(asset_ctxs, list):
            raise HyperliquidApiError("metaAndAssetCtxs の応答形式が不正です。")
        return meta, [item if isinstance(item, dict) else {} for item in asset_ctxs]

    def asset_ctx(self, coin: str) -> dict[str, Any] | None:
        meta, asset_ctxs = self.meta_and_asset_ctxs()
        universe = meta.get("universe")
        if not isinstance(universe, list):
            raise HyperliquidApiError("metaAndAssetCtxs の universe 応答形式が不正です。")
        for index, asset in enumerate(universe):
            if isinstance(asset, dict) and asset.get("name") == coin:
                return asset_ctxs[index] if index < len(asset_ctxs) else None
        return None

    def market_contexts(self, target_symbols: tuple[str, ...]) -> dict[str, dict[str, float | None]]:
        meta, asset_ctxs = self.meta_and_asset_ctxs()
        universe = meta.get("universe")
        if not isinstance(universe, list):
            raise HyperliquidApiError("metaAndAssetCtxs の universe 応答形式が不正です。")

        targets = set(target_symbols)
        contexts: dict[str, dict[str, float | None]] = {}
        for index, asset in enumerate(universe):
            if not isinstance(asset, dict):
                continue
            symbol = str(asset.get("name") or "").upper()
            if symbol not in targets:
                continue
            asset_ctx = asset_ctxs[index] if index < len(asset_ctxs) else {}
            mark_px = _to_float(asset_ctx.get("markPx")) or _to_float(asset_ctx.get("midPx"))
            open_interest_coin = _to_float(asset_ctx.get("openInterest"))
            open_interest_usd = (
                abs(open_interest_coin * mark_px)
                if open_interest_coin is not None and mark_px is not None
                else None
            )
            contexts[symbol] = {
                "mark_px": mark_px,
                "mid_px": _to_float(asset_ctx.get("midPx")),
                "oracle_px": _to_float(asset_ctx.get("oraclePx")),
                "funding": _to_float(asset_ctx.get("funding")),
                "open_interest_coin": open_interest_coin,
                "open_interest_usd": open_interest_usd,
            }
        return contexts

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

    def clearinghouse_state(self, address: str) -> dict[str, Any]:
        data = self.post_info({"type": "clearinghouseState", "user": address})
        if not isinstance(data, dict):
            raise HyperliquidApiError(f"clearinghouseState の応答形式が不正です: address={address}")
        return data

    def candle_snapshot(self, coin: str, interval: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        data = self.post_info(
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            }
        )
        if not isinstance(data, list):
            raise HyperliquidApiError(f"candleSnapshot の応答形式が不正です: coin={coin}")
        return [item for item in data if isinstance(item, dict)]

    def funding_history(self, coin: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        data = self.post_info(
            {
                "type": "fundingHistory",
                "coin": coin,
                "startTime": start_ms,
                "endTime": end_ms,
            }
        )
        if not isinstance(data, list):
            raise HyperliquidApiError(f"fundingHistory の応答形式が不正です: coin={coin}")
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


def _to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
