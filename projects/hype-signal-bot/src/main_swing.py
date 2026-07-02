import sys
import traceback
from datetime import datetime

from .config import load_settings
from .fetcher import get_asset_ctx, get_candles
from .logger import JST, get_logger
from .notifier import send_heartbeat, send_signal
from .signals import check_breakout
from .state import load_state, save_state


def run() -> int:
    logger = get_logger()
    settings = load_settings()
    logger.info(f"[SWING] {settings.coin} ブレイクアウトチェック開始")
    state: dict | None = None

    try:
        candles = get_candles(settings.coin, interval="4h", count=30, only_closed=True)
        if not candles:
            logger.error("ローソク足データ取得失敗")
            return 1

        ctx = get_asset_ctx(settings.coin)
        price = float(ctx.get("markPx", 0)) if ctx else float(candles[-1]["c"])
        state = load_state("swing")

        signal = check_breakout(candles)
        if signal:
            latest_bar_time = str(candles[-1].get("t", "unknown"))
            breakout_key = f"{signal.direction}:{latest_bar_time}"
            if breakout_key != state.get("last_breakout_key"):
                sent = send_signal(
                    signal,
                    coin=settings.coin,
                    webhook_url=settings.discord_webhook_url,
                    dry_run=settings.dry_run,
                )
                # 送信失敗時はキーを更新せず、次回実行で再通知を試みる
                if sent:
                    state["last_breakout_key"] = breakout_key
                logger.info(f"[SWING] ブレイクアウト検知: {signal.direction}")
            else:
                logger.info("[SWING] 同じ4h足のブレイクアウト通知は送信済み")
        else:
            logger.info("[SWING] ブレイクアウトなし")

        now_jst = datetime.now(JST)
        today = now_jst.strftime("%Y-%m-%d")
        if settings.notify_heartbeat and state.get("last_heartbeat_date") != today:
            sent = send_heartbeat(
                coin=settings.coin,
                price=price,
                webhook_url=settings.discord_webhook_url,
                dry_run=settings.dry_run,
            )
            if sent:
                state["last_heartbeat_date"] = today

        state["last_run_jst"] = now_jst.isoformat()
        return 0
    except Exception as exc:
        logger.error(f"[SWING] 実行エラー: {exc}")
        traceback.print_exc()
        return 1
    finally:
        if state is not None:
            try:
                save_state("swing", state)
            except Exception as exc:
                logger.error(f"[SWING] 状態保存失敗: {exc}")


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
