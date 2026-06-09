import sys
import traceback
from datetime import datetime

from .config import load_settings
from .fetcher import get_asset_ctx, get_candles
from .logger import JST, get_logger
from .notifier import send_no_signal_status, send_signal
from .signals import check_funding, check_volume_oi
from .state import load_state, save_state


def _should_send_empty_status(state: dict, now_jst: datetime, interval_minutes: int) -> bool:
    last_sent = state.get("last_empty_notification_jst")
    if not last_sent:
        return True
    try:
        last_sent_at = datetime.fromisoformat(last_sent)
    except ValueError:
        return True
    return (now_jst - last_sent_at).total_seconds() >= interval_minutes * 60


def run() -> int:
    logger = get_logger()
    settings = load_settings()
    logger.info(f"[SCALP] {settings.coin} シグナルチェック開始")

    try:
        ctx = get_asset_ctx(settings.coin)
        if not ctx:
            logger.error(f"{settings.coin} のデータ取得失敗")
            return 1

        candles = get_candles(settings.coin, interval="5m", count=36, only_closed=True)
        state = load_state("scalp")
        signals_found = []

        funding_signal = check_funding(ctx)
        last_funding_direction = state.get("last_funding_direction")
        if funding_signal:
            if funding_signal.direction != last_funding_direction:
                send_signal(
                    funding_signal,
                    coin=settings.coin,
                    webhook_url=settings.discord_webhook_url,
                    dry_run=settings.dry_run,
                )
                signals_found.append(funding_signal.kind)
            state["last_funding_direction"] = funding_signal.direction
        else:
            state["last_funding_direction"] = None

        prev_oi = state.get("last_oi")
        volume_oi_signal = check_volume_oi(ctx, prev_oi, candles)
        if volume_oi_signal:
            send_signal(
                volume_oi_signal,
                coin=settings.coin,
                webhook_url=settings.discord_webhook_url,
                dry_run=settings.dry_run,
            )
            signals_found.append(volume_oi_signal.kind)

        price = float(ctx.get("markPx", 0))
        now_jst = datetime.now(JST)
        state["last_oi"] = float(ctx.get("openInterest", 0))
        state["last_run_jst"] = now_jst.isoformat()

        if signals_found:
            logger.info(f"[SCALP] シグナル検知: {signals_found}")
        else:
            logger.info("[SCALP] シグナルなし")
            if settings.notify_empty and _should_send_empty_status(
                state,
                now_jst,
                settings.empty_notification_interval_minutes,
            ):
                send_no_signal_status(
                    coin=settings.coin,
                    price=price,
                    checked_at_jst=now_jst,
                    webhook_url=settings.discord_webhook_url,
                    dry_run=settings.dry_run,
                )
                state["last_empty_notification_jst"] = now_jst.isoformat()

        save_state("scalp", state)
        return 0
    except Exception as exc:
        logger.error(f"[SCALP] 実行エラー: {exc}")
        traceback.print_exc()
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
