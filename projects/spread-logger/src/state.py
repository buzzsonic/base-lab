"""実行間で持ち越す状態: (1) 週末に使うUSDJPY参照レート(金曜終値) (2) アラートのクールダウン。

coin-scoutのstate.pyと同様、読み込み失敗時は例外を投げずNone/空を返して呼び出し側に処理させる。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path(".state") / "spread_logger_state.json"


def _empty_state() -> dict[str, Any]:
    return {"fx": None, "alerts": {}}


def load_state(logger: Any, path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        logger.info("前回状態なし(初回実行)。")
        return _empty_state()

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"前回状態を読み込めませんでした: {exc}")
        return _empty_state()

    if not isinstance(data, dict):
        logger.warning("前回状態の形式が不正です。")
        return _empty_state()

    data.setdefault("fx", None)
    data.setdefault("alerts", {})
    if not isinstance(data["alerts"], dict):
        data["alerts"] = {}
    return data


def save_state(state: dict[str, Any], logger: Any, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(f"状態保存: {path}")


def save_fx_rate(state: dict[str, Any], rate: float, fetched_at_jst: datetime) -> None:
    state["fx"] = {
        "rate": rate,
        "fetched_at_jst": fetched_at_jst.strftime("%Y-%m-%d %H:%M:%S JST"),
        "weekday_ja": "月火水木金土日"[fetched_at_jst.weekday()],
    }


def get_saved_fx_rate(state: dict[str, Any]) -> dict[str, Any] | None:
    fx = state.get("fx")
    return fx if isinstance(fx, dict) else None


def is_alert_in_cooldown(
    state: dict[str, Any], alert_key: str, now: datetime, cooldown_hours: float
) -> bool:
    last_fired_raw = state.get("alerts", {}).get(alert_key)
    if not last_fired_raw:
        return False
    try:
        last_fired = datetime.fromisoformat(last_fired_raw)
    except ValueError:
        return False
    elapsed_hours = (now - last_fired).total_seconds() / 3600
    return elapsed_hours < cooldown_hours


def mark_alert_fired(state: dict[str, Any], alert_key: str, now: datetime) -> None:
    state.setdefault("alerts", {})[alert_key] = now.isoformat()
