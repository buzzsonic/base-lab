import sys
import traceback
from datetime import datetime

from shared.discord import DiscordNotifyError, send_discord_message
from shared.envtools import ConfigError
from shared.hyperliquid import HyperliquidClient
from shared.logging_utils import JST, get_logger

from .config import load_settings
from .detect import build_report, fetch_volume_baselines
from .notify import format_digest, format_error_message
from .state import load_state, save_state
from .universe import build_watchlist


def run() -> int:
    logger = get_logger("coin-scout")
    settings = None

    try:
        settings = load_settings()
        logger.info(
            "設定読み込み完了: "
            f"min_cex_volume_usd={settings.min_cex_volume_usd:g}, "
            f"volume_spike_ratio={settings.volume_spike_ratio:g}, "
            f"price_move_min_pct={settings.price_move_min_pct:g}, "
            f"funding_apr_alert_pct={settings.funding_apr_alert_pct:g}, "
            f"oi_change_alert_pct={settings.oi_change_alert_pct:g}, "
            f"dry_run={settings.dry_run}"
        )

        run_at_jst = datetime.now(JST)
        client = HyperliquidClient(logger=logger)

        watchlist, all_coins = build_watchlist(client, settings.min_cex_volume_usd, logger)
        baselines = fetch_volume_baselines(
            client, [asset["coin"] for asset in watchlist], settings.baseline_days, logger
        )
        previous_state = load_state(logger=logger)

        report = build_report(watchlist, all_coins, baselines, previous_state, settings)
        logger.info(
            f"検知結果: 発火{report['total_fired']}銘柄, 新規上場{len(report['new_listings'])}銘柄"
        )

        message = format_digest(report, run_at_jst)
        send_discord_message(
            webhook_url=settings.discord_webhook_url,
            message=message,
            dry_run=settings.dry_run,
            logger=logger,
        )

        # 通知成功後に保存する: 送信前に保存すると、送信失敗時に新規上場・OI変化が未通知のまま既知扱いになる
        current_oi = {
            asset["coin"]: asset["open_interest_usd"]
            for asset in watchlist
            if asset["open_interest_usd"]
        }
        save_state(all_coins=all_coins, oi_usd=current_oi, run_at_jst=run_at_jst, logger=logger)
        logger.info("処理完了")
        return 0
    except ConfigError as exc:
        logger.error(f"設定エラー: {exc}")
        return 2
    except Exception as exc:
        logger.error(f"実行エラー: {exc}")
        traceback.print_exc()
        _notify_error(settings, exc, logger)
        return 1


def _notify_error(settings, exc: Exception, logger) -> None:
    """実行エラーを無音にしないためのDiscord通知。通知自体の失敗は握りつぶす。"""
    if settings is None or settings.dry_run or not settings.discord_webhook_url:
        return
    try:
        send_discord_message(
            webhook_url=settings.discord_webhook_url,
            message=format_error_message(str(exc), datetime.now(JST)),
            dry_run=False,
            logger=logger,
        )
    except DiscordNotifyError as notify_exc:
        logger.error(f"エラー通知の送信にも失敗: {notify_exc}")


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
