"""USDJPY参照レートの取得。

平日(JST月〜金)は open.er-api.com から実勢レートを取得し、.stateに保存する。
週末(JST土日)はAPIを叩かず、平日に保存しておいた最新の値(=直近の金曜値)を使う。
土日から状態を持たずに使い始めた場合(初回実行が週末等)は、フォールバックとして
その場でAPIを叩く(「金曜終値」の前提が崩れる旨をログに残す)。
"""

from datetime import datetime
from typing import Any

import requests

from .config import FX_REFERENCE_URL

TIMEOUT_SECONDS = 15
WEEKEND_WEEKDAYS = (5, 6)  # datetime.weekday(): 5=土, 6=日


def _fetch_live_rate(logger: Any) -> float | None:
    try:
        response = requests.get(FX_REFERENCE_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        rate = payload.get("rates", {}).get("JPY")
        if rate is None:
            logger.warning(f"USDJPY参照レート: 応答にJPYがありません: {payload}")
            return None
        return float(rate)
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning(f"USDJPY参照レートの取得に失敗: {exc}")
        return None


def get_reference_usdjpy(
    now_jst: datetime, state: dict[str, Any], logger: Any
) -> tuple[float | None, bool, str]:
    """(参照USDJPYレート, 週末フラグ, 由来メモ) を返す。取得不能ならレートはNone。"""
    is_weekend = now_jst.weekday() in WEEKEND_WEEKDAYS

    if not is_weekend:
        rate = _fetch_live_rate(logger)
        if rate is not None:
            from .state import save_fx_rate

            save_fx_rate(state, rate, now_jst)
            return rate, False, "平日実勢レート(open.er-api.com)"
        logger.warning("平日レート取得失敗。直前の保存値があればフォールバックします。")

    from .state import get_saved_fx_rate

    saved = get_saved_fx_rate(state)
    if saved is not None:
        note = "金曜終値(保存値)" if is_weekend else "平日レート取得失敗のため直前保存値を使用"
        return float(saved["rate"]), is_weekend, f"{note} @ {saved.get('fetched_at_jst', '不明')}"

    if is_weekend:
        logger.warning("週末だが保存済みの金曜値がありません。フォールバックでAPIを直接叩きます。")
        rate = _fetch_live_rate(logger)
        if rate is not None:
            return rate, True, "保存値なしのため週末にAPIを直接取得(金曜終値ではない)"

    logger.error("USDJPY参照レートを取得できませんでした。")
    return None, is_weekend, "取得不能"
