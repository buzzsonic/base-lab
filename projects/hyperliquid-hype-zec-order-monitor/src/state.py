import json
from pathlib import Path
from typing import Any


def load_snapshot(path: Path, logger: Any) -> dict[str, Any] | None:
    if not path.exists():
        logger.info(f"前回スナップショットなし: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"前回スナップショットを読み込めません: {exc}")
        return None
    if not isinstance(data, dict):
        logger.warning("前回スナップショット形式が不正です。")
        return None
    return data


def save_snapshot(path: Path, snapshot: dict[str, Any], logger: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"スナップショット保存: {path}")
