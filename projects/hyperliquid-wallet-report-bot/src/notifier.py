import json
import urllib.error
import urllib.request
from typing import Any


class DiscordNotifyError(RuntimeError):
    pass


def send_discord_message(webhook_url: str, message: str, dry_run: bool, logger: Any) -> None:
    if dry_run:
        logger.info("DRY_RUN=true のためDiscord送信はスキップします。")
        logger.info(f"送信予定メッセージ:\n{message}")
        return

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": message}, ensure_ascii=False).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "AICompanyHyperliquidWalletReportBot/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 300:
                raise DiscordNotifyError(f"Discord Webhook送信に失敗しました: status={resp.status}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DiscordNotifyError(f"Discord Webhook送信に失敗しました: {exc}") from exc

