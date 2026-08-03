import sys
import traceback
from datetime import datetime

from shared.discord import DiscordNotifyError, send_discord_message
from shared.envtools import ConfigError
from shared.hyperliquid import HyperliquidClient
from shared.logging_utils import JST, UTC, get_logger

from .config import HL_SPOT_BASIS_TARGETS, load_settings
from .csv_writer import append_row, build_row
from .fetch_domestic import fetch_all_domestic
from .fetch_fx import get_reference_usdjpy
from .fetch_hyperliquid import fetch_perp_contexts, fetch_spot_mids
from .fetch_nado import fetch_nado_perps
from .fetch_variational import fetch_variational_perps
from .metrics import build_metrics
from .notify import apply_cooldowns, evaluate_alerts, format_alert_message, format_error_message
from .state import load_state, save_state


def run() -> int:
    logger = get_logger("spread-logger")
    settings = None

    try:
        settings = load_settings()
        logger.info(
            "設定読み込み完了: "
            f"coins={','.join(settings.coins)}, "
            f"effective_jpy_dev_alert_pct={settings.effective_jpy_dev_alert_pct:g}, "
            f"domestic_cross_alert_pct={settings.domestic_cross_alert_pct:g}, "
            f"funding_apr_alert_pct={settings.funding_apr_alert_pct:g}, "
            f"hl_basis_alert_pct={settings.hl_basis_alert_pct:g}, "
            f"pointfarm_enabled={settings.pointfarm_enabled}, "
            f"fr_spread_alert_apr_pct={settings.fr_spread_alert_apr_pct:g}, "
            f"alert_cooldown_hours={settings.alert_cooldown_hours:g}, "
            f"dry_run={settings.dry_run}"
        )

        run_at_utc = datetime.now(UTC)
        run_at_jst = datetime.now(JST)
        state = load_state(logger=logger)

        domestic = fetch_all_domestic(settings.coins, logger)
        domestic_hit_count = sum(len(v) for v in domestic.values())

        # 列構成は POINTFARM_ENABLED に関係なく固定する。無効化で列が消えると
        # 月次CSVのスキーマが縮んで追記がずれるため、取得だけを止めて値は空欄にする。
        pointfarm_coins = settings.pointfarm_coins

        client = HyperliquidClient(logger=logger)
        perp_targets = tuple(
            sorted(set(settings.coins) | set(HL_SPOT_BASIS_TARGETS.values()) | set(pointfarm_coins))
        )
        hl_perp = fetch_perp_contexts(client, perp_targets, logger)
        hl_spot_mids = fetch_spot_mids(client, logger)

        # ポイ活DEXは片方が落ちても残りの記録を続ける(HLと国内取引所が本体のため)
        variational: dict = {}
        nado: dict = {}
        if settings.pointfarm_enabled:
            variational = fetch_variational_perps(pointfarm_coins, logger)
            nado = fetch_nado_perps(pointfarm_coins, logger)
            logger.info(f"ポイ活DEX取得: Variational {len(variational)}銘柄 / Nado {len(nado)}銘柄")
        else:
            logger.info("POINTFARM_ENABLED=false のためポイ活DEXの取得をスキップします(該当列は空欄)")

        if domestic_hit_count == 0 and not hl_perp:
            raise RuntimeError("国内取引所・Hyperliquidともに全滅しました。記録できる値がありません。")

        usdjpy_ref, is_weekend, fx_source = get_reference_usdjpy(run_at_jst, state, logger)
        logger.info(f"USDJPY参照レート: {usdjpy_ref} (週末={is_weekend}, 由来={fx_source})")

        metrics = build_metrics(
            settings.coins,
            domestic,
            hl_perp,
            hl_spot_mids,
            usdjpy_ref,
            pointfarm_coins,
            variational,
            nado,
        )

        row = build_row(
            settings.coins,
            run_at_utc,
            run_at_jst,
            usdjpy_ref,
            is_weekend,
            fx_source,
            domestic,
            metrics,
            pointfarm_coins,
        )
        csv_path = append_row(row, settings.coins, run_at_jst, logger, pointfarm_coins)
        logger.info(f"CSV出力: {csv_path}")

        alerts = evaluate_alerts(settings.coins, metrics, settings, state, run_at_jst)
        if alerts:
            message = format_alert_message(alerts, run_at_jst)
            try:
                send_discord_message(
                    webhook_url=settings.discord_webhook_url,
                    message=message,
                    dry_run=settings.dry_run,
                    logger=logger,
                )
                apply_cooldowns(alerts, state, run_at_jst)
            except DiscordNotifyError as exc:
                logger.error(f"アラート通知の送信に失敗(CSVへの記録は完了済み): {exc}")
        else:
            logger.info("アラートなし(閾値未超過、またはクールダウン中)")

        save_state(state, logger=logger)
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
