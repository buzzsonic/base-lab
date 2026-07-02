from datetime import datetime, timedelta, timezone


JST = timezone(timedelta(hours=9))
UTC = timezone.utc


class ActionLogger:
    def __init__(self, name: str = "base-lab") -> None:
        self.name = name

    def _log(self, level: str, message: str) -> None:
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        print(f"{now} [{level}] {self.name}: {message}", flush=True)

    def info(self, message: str) -> None:
        self._log("INFO", message)

    def warning(self, message: str) -> None:
        self._log("WARN", message)

    def error(self, message: str) -> None:
        self._log("ERROR", message)


def get_logger(name: str = "base-lab") -> ActionLogger:
    return ActionLogger(name)
