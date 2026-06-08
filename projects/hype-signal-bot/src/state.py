import json
from pathlib import Path
from typing import Any


STATE_DIR = Path(".state")


def load_state(name: str) -> dict[str, Any]:
    path = STATE_DIR / f"{name}.json"
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def save_state(name: str, state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{name}.json"
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
    temp_path.replace(path)
