import time
from typing import Any

import requests


class DiscordNotifyError(RuntimeError):
    pass


def send_discord_message(
    webhook_url: str,
    message: str,
    dry_run: bool,
    logger: Any,
    retries: int = 2,
) -> None:
    """テキストメッセージをDiscord Webhookへ送信する。最終的に失敗した場合はDiscordNotifyErrorを投げる。"""
    if not message:
        logger.info("通知メッセージなし")
        return
    if dry_run:
        logger.info("DRY_RUN=true のためDiscord送信はスキップします。")
        logger.info(f"送信予定メッセージ:\n{message}")
        return

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(webhook_url, json={"content": message}, timeout=10)
            response.raise_for_status()
            return
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                logger.warning(f"Discord送信リトライ: attempt={attempt}/{retries}, error={exc}")
                time.sleep(3)

    raise DiscordNotifyError(f"Discord Webhook送信に失敗しました: {last_error}") from last_error


def send_discord_embeds(
    embeds: list[dict],
    *,
    webhook_url: str | None,
    dry_run: bool,
    label: str,
    logger: Any | None = None,
    retries: int = 2,
) -> bool:
    """embedをDiscord Webhookへ送信する。例外は投げず成否をboolで返す。"""

    def _log(message: str) -> None:
        if logger is not None:
            logger.info(message)
        else:
            print(message)

    if dry_run:
        _log(f"[DRY_RUN] Discord通知予定: {label}")
        _log(str(embeds))
        return True
    if not webhook_url:
        _log("[WARN] DISCORD_WEBHOOK_URL が未設定です")
        return False

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(webhook_url, json={"embeds": embeds}, timeout=15)
            response.raise_for_status()
            _log(f"[OK] Discord通知送信: {label}")
            return True
        except requests.RequestException as exc:
            if attempt < retries:
                _log(f"[WARN] Discord通知リトライ: {label} / {exc}")
                time.sleep(3)
            else:
                _log(f"[ERROR] Discord通知失敗: {label} / {exc}")
    return False
