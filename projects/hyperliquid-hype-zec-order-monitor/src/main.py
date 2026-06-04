import sys
import traceback

from .config import ConfigError, load_config
from .hyperliquid_client import HyperliquidClient
from .leaderboard import fetch_leaderboard_wallets
from .logger import get_logger
from .monitor import build_report, build_snapshot
from .notifier import format_report_message, send_discord_message
from .state import load_snapshot, save_snapshot


def run() -> int:
    logger = get_logger()

    try:
        settings = load_config()
        logger.info(
            "設定読み込み完了: "
            f"limit={settings.leaderboard_limit}, targets={','.join(settings.target_symbols)}, "
            f"liq_band={settings.liquidation_band_pct:g}%, "
            f"dry_run={settings.dry_run}, notify_empty={settings.notify_empty}"
        )

        previous = load_snapshot(path=settings.state_path, logger=logger)
        client = HyperliquidClient(request_sleep_seconds=settings.request_sleep_seconds, logger=logger)
        market_contexts = client.market_contexts(settings.target_symbols)
        mids = {symbol: context.get("mark_px") for symbol, context in market_contexts.items()}
        missing_mids = [symbol for symbol in settings.target_symbols if mids.get(symbol) is None]
        if missing_mids:
            mids.update(client.all_mids())
        wallets = fetch_leaderboard_wallets(limit=settings.leaderboard_limit, logger=logger)
        snapshot = build_snapshot(
            client=client,
            wallets=wallets,
            mids=mids,
            market_contexts=market_contexts,
            settings=settings,
            logger=logger,
        )
        report = build_report(current=snapshot, previous=previous, settings=settings)
        save_snapshot(path=settings.state_path, snapshot=snapshot, logger=logger)

        stats = report["stats"]
        logger.info(
            "判定完了: "
            f"ポジション={stats['current_positions']}, 清算候補={stats['liquidation_levels']}, "
            f"markets={stats['markets']}, errors={stats['errors']}"
        )
        message = format_report_message(report=report, settings=settings)
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
