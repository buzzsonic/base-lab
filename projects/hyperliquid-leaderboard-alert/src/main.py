import sys
import traceback
from datetime import datetime

from .config import ConfigError, load_config
from .detector import detect_alerts
from .hyperliquid_client import HyperliquidClient
from .leaderboard import fetch_leaderboard_positions
from .logger import JST, get_logger
from .notifier import format_alert_message, send_discord_message


def run() -> int:
    logger = get_logger()

    try:
        settings = load_config()
        logger.info(
            "設定読み込み完了: "
            f"mode={settings.alert_mode}, limit={settings.leaderboard_limit}, "
            f"target_side={settings.target_side}, min_abs_position_usd={settings.min_abs_position_usd:g}, "
            f"dry_run={settings.dry_run}"
        )

        client = HyperliquidClient(logger=logger)
        snapshots = fetch_leaderboard_positions(client=client, limit=settings.leaderboard_limit, logger=logger)
        failed_wallets = sum(1 for row in snapshots if row.get("error"))
        if failed_wallets:
            logger.warning(f"取得失敗ウォレット: {failed_wallets}件")

        alerts = detect_alerts(snapshots=snapshots, settings=settings)
        if not alerts:
            logger.info("通知対象なし")
            return 0

        logger.info(f"通知対象あり: {len(alerts)}件")
        message = format_alert_message(alerts=alerts, run_at_jst=datetime.now(JST), settings=settings)
        send_discord_message(
            webhook_url=settings.discord_webhook_url,
            message=message,
            dry_run=settings.dry_run,
            logger=logger,
        )
        logger.info("処理完了")
        return 0
    except ConfigError as exc:
        logger.error(f"設定エラー: {exc}")
        return 2
    except Exception as exc:
        logger.error(f"実行エラー: {exc}")
        traceback.print_exc()
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
