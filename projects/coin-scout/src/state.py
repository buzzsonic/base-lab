import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path(".state") / "scout_state.json"


def load_state(logger: Any, path: Path = DEFAULT_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        logger.info("前回状態なし。OI変化・新規上場の判定は次回実行から有効です。")
        return None

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"前回状態を読み込めませんでした: {exc}")
        return None

    if not isinstance(data, dict) or not isinstance(data.get("coins"), list) or not isinstance(data.get("oi_usd"), dict):
        logger.warning("前回状態の形式が不正です。OI変化・新規上場の判定はスキップします。")
        return None

    logger.info(f"前回状態読み込み: {len(data['coins'])}銘柄 ({data.get('generated_at_jst', '不明')})")
    return data


def save_state(
    all_coins: list[str],
    oi_usd: dict[str, float],
    run_at_jst: datetime,
    logger: Any,
    path: Path = DEFAULT_STATE_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_jst": run_at_jst.strftime("%Y-%m-%d %H:%M:%S JST"),
        "coins": sorted(all_coins),
        "oi_usd": {coin: round(value, 2) for coin, value in sorted(oi_usd.items())},
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(f"今回状態保存: {path} ({len(all_coins)}銘柄)")
