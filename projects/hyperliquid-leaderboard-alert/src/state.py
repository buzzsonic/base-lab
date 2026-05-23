import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_STATE_PATH = Path(".state") / "leaderboard_snapshot.json"


def load_snapshot(logger: Any, path: Path = DEFAULT_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        logger.info("前回スナップショットなし。新規・増加判定は次回実行から有効です。")
        return None

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"前回スナップショットを読み込めませんでした: {exc}")
        return None

    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        logger.warning("前回スナップショットの形式が不正です。新規・増加判定はスキップします。")
        return None

    logger.info(f"前回スナップショット読み込み: {len(data['positions'])}ポジション")
    return data


def save_snapshot(positions: list[dict[str, Any]], run_at_jst: datetime, logger: Any, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_jst": run_at_jst.strftime("%Y-%m-%d %H:%M:%S JST"),
        "positions": positions,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(f"今回スナップショット保存: {path} ({len(positions)}ポジション)")
