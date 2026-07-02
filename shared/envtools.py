import os


class ConfigError(ValueError):
    pass


def read_str(name: str, default: str | None = None) -> str:
    raw = os.environ.get(name, default)
    return "" if raw is None else str(raw).strip()


def read_int(name: str, default: int) -> int:
    raw = read_str(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} は整数で指定してください。現在値: {raw!r}") from exc


def read_float(name: str, default: float) -> float:
    raw = read_str(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} は数値で指定してください。現在値: {raw!r}") from exc


def read_bool(name: str, default: bool) -> bool:
    raw = read_str(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"{name} は true または false で指定してください。現在値: {raw!r}")
