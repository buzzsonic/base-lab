import sys
import traceback
from datetime import datetime

from .config import ConfigError, load_config
from .detector import build_position_report
from .hyperliquid_client import HyperliquidClient
from .leaderboard import fetch_leaderboard_positions
from .logger import JST, get_logger
from .notifier import format_position_report_message, send_discord_message
from .state import load_snapshot, save_snapshot


def run() -> int:
    logger = get_logger()

    try:
        settings = load_config()
        logger.info(
            "設定読み込み完了: "
            f"mode={settings.alert_mode}, limit={settings.leaderboard_limit}, "
            f"target_side={settings.target_side}, min_abs_position_usd={settings.min_abs_position_usd:g}, "
            f"min_position_change_usd={settings.min_position_change_usd:g}, "
            f"dry_run={settings.dry_run}"
        )

        run_at_jst = datetime.now(JST)
        client = HyperliquidClient(logger=logger)
        mids = client.all_mids()
        logger.info(f"現在価格取得: {len(mids)}銘柄")
        previous_snapshot = load_snapshot(logger=logger)
        snapshots = fetch_leaderboard_positions(client=client, limit=settings.leaderboard_limit, logger=logger)
        failed_wallets = sum(1 for row in snapshots if row.get("error"))
        if failed_wallets:
            logger.warning(f"取得失敗ウォレット: {failed_wallets}件")

        report = build_position_report(
            snapshots=snapshots,
            previous_snapshot=previous_snapshot,
            mids=mids,
            settings=settings,
        )
        save_snapshot(positions=report["snapshot_positions"], run_at_jst=run_at_jst, logger=logger)

        stats = report["stats"]
        if stats["current_positions"] == 0 and stats["new_positions"] == 0 and stats["increased_positions"] == 0:
            logger.info("通知対象なし")
            return 0

        logger.info(
            "通知対象あり: "
            f"現在={stats['current_positions']}件, 新規={stats['new_positions']}件, 増加={stats['increased_positions']}件"
        )
        message = format_position_report_message(report=report, run_at_jst=run_at_jst, settings=settings)
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
