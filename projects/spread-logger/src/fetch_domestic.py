"""国内取引所4所(bitFlyer/bitbank/GMOコイン/Coincheck)の公開ティッカーAPIからbest bid/askを取得する。

各取引所ごとに実際の取扱ペアが異なるため(例: bitFlyerはBTC/ETH/XRPのみ、CoincheckはLTC非対応)、
取得できなかった銘柄は例外を投げずに欠測として扱い、呼び出し側でログに残してCSVを空欄にする。
"""

from typing import Any

import requests

TIMEOUT_SECONDS = 15

BITFLYER_MARKETS_URL = "https://api.bitflyer.com/v1/markets"
BITFLYER_TICKER_URL = "https://api.bitflyer.com/v1/ticker"
BITBANK_TICKERS_URL = "https://public.bitbank.cc/tickers"
GMO_TICKER_URL = "https://api.coin.z.com/public/v1/ticker"
COINCHECK_TICKER_URL = "https://coincheck.com/api/ticker"


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_bitflyer(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float]]:
    """bitFlyerのbest bid/askをコイン名→{"bid":.., "ask":..}で返す(取扱なしは黙ってスキップ)。"""
    result: dict[str, dict[str, float]] = {}
    try:
        response = requests.get(BITFLYER_MARKETS_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        markets = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"bitFlyer: 銘柄一覧の取得に失敗: {exc}")
        return result

    available_products = {
        str(m.get("product_code")) for m in markets if isinstance(m, dict) and m.get("product_code")
    }

    for coin in coins:
        product_code = f"{coin}_JPY"
        if product_code not in available_products:
            logger.info(f"bitFlyer: {coin} は取扱なし(スキップ)")
            continue
        try:
            response = requests.get(
                BITFLYER_TICKER_URL,
                params={"product_code": product_code},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            bid = _to_float(data.get("best_bid"))
            ask = _to_float(data.get("best_ask"))
            if bid is None or ask is None:
                logger.warning(f"bitFlyer: {coin} の応答にbid/askがありません: {data}")
                continue
            result[coin] = {"bid": bid, "ask": ask}
        except (requests.RequestException, ValueError) as exc:
            logger.warning(f"bitFlyer: {coin} の取得に失敗: {exc}")
    return result


def fetch_bitbank(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float]]:
    """bitbankのbest bid/ask(sell=ask, buy=bid)をコイン名→{"bid":.., "ask":..}で返す。"""
    result: dict[str, dict[str, float]] = {}
    try:
        response = requests.get(BITBANK_TICKERS_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"bitbank: 一括ティッカーの取得に失敗: {exc}")
        return result

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        logger.warning("bitbank: 応答の形式が不正です。")
        return result

    by_pair = {str(item.get("pair")): item for item in data if isinstance(item, dict)}

    for coin in coins:
        pair = f"{coin.lower()}_jpy"
        item = by_pair.get(pair)
        if item is None:
            logger.info(f"bitbank: {coin} は取扱なし(スキップ)")
            continue
        ask = _to_float(item.get("sell"))
        bid = _to_float(item.get("buy"))
        if bid is None or ask is None:
            logger.warning(f"bitbank: {coin} の応答にbid/askがありません: {item}")
            continue
        result[coin] = {"bid": bid, "ask": ask}
    return result


def fetch_gmo(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float]]:
    """GMOコインの現物(_JPY)ペアのbest bid/askをコイン名→{"bid":.., "ask":..}で返す。"""
    result: dict[str, dict[str, float]] = {}
    try:
        response = requests.get(GMO_TICKER_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"GMOコイン: 一括ティッカーの取得に失敗: {exc}")
        return result

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        logger.warning("GMOコイン: 応答の形式が不正です。")
        return result

    by_symbol = {str(item.get("symbol")): item for item in data if isinstance(item, dict)}

    for coin in coins:
        symbol = f"{coin}_JPY"
        item = by_symbol.get(symbol)
        if item is None:
            logger.info(f"GMOコイン: {coin} は現物取扱なし(スキップ)")
            continue
        bid = _to_float(item.get("bid"))
        ask = _to_float(item.get("ask"))
        if bid is None or ask is None:
            logger.warning(f"GMOコイン: {coin} の応答にbid/askがありません: {item}")
            continue
        result[coin] = {"bid": bid, "ask": ask}
    return result


def fetch_coincheck(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, float]]:
    """Coincheckのbest bid/askをコイン名→{"bid":.., "ask":..}で返す。

    公式ドキュメントはbtc_jpy以外のtickerを謳っていないが、実際にはeth_jpy/xrp_jpy/sol_jpy/doge_jpy等も
    ?pair= で有効なJSONを返す(LTCは非対応でHTMLの404ページが返る)。JSON化に失敗する、またはbid/askが
    欠けている場合は非対応とみなして黙ってスキップする。
    """
    result: dict[str, dict[str, float]] = {}
    for coin in coins:
        pair = f"{coin.lower()}_jpy"
        try:
            response = requests.get(
                COINCHECK_TICKER_URL, params={"pair": pair}, timeout=TIMEOUT_SECONDS
            )
            if response.status_code != 200:
                logger.info(f"Coincheck: {coin} は取扱なし(status={response.status_code}, スキップ)")
                continue
            data = response.json()
        except (requests.RequestException, ValueError):
            logger.info(f"Coincheck: {coin} は取扱なし(非JSON応答、スキップ)")
            continue
        bid = _to_float(data.get("bid")) if isinstance(data, dict) else None
        ask = _to_float(data.get("ask")) if isinstance(data, dict) else None
        if bid is None or ask is None:
            logger.info(f"Coincheck: {coin} は取扱なし(bid/askなし、スキップ)")
            continue
        result[coin] = {"bid": bid, "ask": ask}
    return result


# 取引所名 → 取得関数。main/metricsから共通のループで扱えるようにする。
FETCHERS = {
    "bitflyer": fetch_bitflyer,
    "bitbank": fetch_bitbank,
    "gmo": fetch_gmo,
    "coincheck": fetch_coincheck,
}


def fetch_all_domestic(coins: tuple[str, ...], logger: Any) -> dict[str, dict[str, dict[str, float]]]:
    """取引所名 → {コイン名: {"bid":.., "ask":..}} を返す。1取引所が全滅しても他は続行する。"""
    all_data: dict[str, dict[str, dict[str, float]]] = {}
    for exchange, fetcher in FETCHERS.items():
        try:
            all_data[exchange] = fetcher(coins, logger)
        except Exception as exc:  # noqa: BLE001 - 1取引所の想定外エラーで全体を落とさない
            logger.error(f"{exchange}: 予期しないエラーで取得スキップ: {exc}")
            all_data[exchange] = {}
        logger.info(f"{exchange}: {len(all_data[exchange])}/{len(coins)}銘柄取得")
    return all_data
