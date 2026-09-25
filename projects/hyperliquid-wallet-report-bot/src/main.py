import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .analytics import build_period_stats, daily_window, evaluate_risk, score_daily, score_weekly, weekly_window
from .config import ConfigError, Settings, load_config
from .formatter import format_behavior_risk_message, format_daily_report, format_risk_message, format_weekly_report, write_report
from .hyperliquid_client import HyperliquidApiError, HyperliquidClient
from .logger import JST, get_logger
from .notifier import DiscordNotifyError, send_discord_message
from .parser import parse_fills, parse_snapshot
from .sample_data import SAMPLE_FILLS, SAMPLE_SNAPSHOT
from .storage import WalletStore
from .risk_engine import aggregate_level, equity_stats, evaluate_behavior, reconstruct_cycles, LEVELS
from .dashboard import build_dashboard


def run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logger = get_logger()

    try:
        settings = load_config(db_path=args.db_path, reports_dir=args.reports_dir, dry_run_override=args.dry_run)
        store = WalletStore(settings.db_path)
        try:
            if args.mode == "discord-test":
                return run_discord_test(settings=settings, logger=logger)
            if args.mode == "risk":
                return run_risk(settings=settings, store=store, sample=args.sample, logger=logger)
            if args.mode == "daily":
                return run_daily(settings=settings, store=store, sample=args.sample, date_text=args.date, logger=logger)
            if args.mode == "weekly":
                return run_weekly(settings=settings, store=store, sample=args.sample, date_text=args.date, logger=logger)
            if args.mode == "snapshot":
                return run_snapshot(settings=settings, store=store, sample=args.sample, logger=logger)
            if args.mode == "dashboard":
                return run_dashboard(settings=settings, store=store, sample=args.sample, logger=logger)
            raise ConfigError(f"unsupported mode: {args.mode}")
        finally:
            store.close()
    except (ConfigError, HyperliquidApiError, DiscordNotifyError) as exc:
        logger.error(str(exc))
        return 2
    except Exception as exc:
        logger.error(f"実行エラー: {exc}")
        raise


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hyperliquid wallet report bot")
    parser.add_argument("mode", choices=["discord-test", "risk", "daily", "weekly", "snapshot", "dashboard"], help="実行モード")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Discord送信せずログに表示する")
    parser.add_argument("--sample", action="store_true", help="Hyperliquid APIを使わずサンプルデータで実行する")
    parser.add_argument("--date", help="daily/weeklyの基準日 YYYY-MM-DD")
    parser.add_argument("--db-path", help="SQLite DB path")
    parser.add_argument("--reports-dir", help="report output directory")
    return parser


def run_discord_test(settings: Settings, logger: object) -> int:
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    message = "\n".join(
        [
            "【Hyperliquid Wallet Report Bot Test】",
            f"時刻: {now}",
            "Discord接続テストです。",
            "このメッセージが見えていればWebhook送信は動いています。",
            "売買・送金・注文変更は行っていません。",
        ]
    )
    send_discord_message(settings.discord_webhook_url, message, settings.dry_run, logger)
    return 0


def run_snapshot(settings: Settings, store: WalletStore, sample: bool, logger: object) -> int:
    payload, fills = fetch_payload(settings, sample=sample, start_ms=None, end_ms=None, logger=logger)
    snapshot = parse_snapshot(payload)
    parsed_fills = parse_fills(fills)
    snapshot_id = store.save_snapshot(snapshot, payload)
    store.save_market_contexts(snapshot.time_ms, payload.get("market"))
    inserted = store.save_fills(parsed_fills)
    logger.info(f"snapshot saved: id={snapshot_id}, positions={len(snapshot.positions)}, new_fills={inserted}")
    refresh_dashboard(settings, store, snapshot.time_ms, logger)
    return 0


def run_dashboard(settings: Settings, store: WalletStore, sample: bool, logger: object) -> int:
    if sample:
        run_snapshot(settings, store, sample=True, logger=logger)
        parsed = parse_fills(SAMPLE_FILLS)
        store.replace_trades(reconstruct_cycles(parsed))
    rows = store.all_snapshot_rows()
    as_of_ms = int(rows[-1]["time_ms"]) if rows else int(datetime.now(JST).timestamp() * 1000)
    refresh_dashboard(settings, store, as_of_ms, logger)
    return 0


def refresh_dashboard(settings: Settings, store: WalletStore, as_of_ms: int, logger: object) -> None:
    path = build_dashboard(store, settings.reports_dir / "dashboard" / "index.html", as_of_ms)
    logger.info(f"dashboard saved: {path}")


def run_risk(settings: Settings, store: WalletStore, sample: bool, logger: object) -> int:
    now_jst = datetime.now(JST)
    window = daily_window(now_jst=now_jst, cutoff_hour=settings.daily_cutoff_hour_jst)
    history_start = int((now_jst - timedelta(days=14)).timestamp() * 1000)
    payload, fills = fetch_payload(settings, sample=sample, start_ms=history_start, end_ms=window.end_ms, logger=logger)
    snapshot = parse_snapshot(payload)
    parsed_fills = parse_fills(fills)
    store.save_snapshot(snapshot, payload)
    store.save_market_contexts(snapshot.time_ms, payload.get("market"))
    store.save_fills(parsed_fills)

    history_fills = store.fills_between(history_start, window.end_ms)
    fills_today = [f for f in history_fills if f.time_ms >= window.start_ms]
    cycles = reconstruct_cycles(history_fills)
    store.replace_trades(cycles)
    snapshots = store.snapshot_range(window.start_ms, snapshot.time_ms)
    eq = equity_stats(snapshot, snapshots, window.start_ms, fills_today)
    store.update_daily_stats({"day_jst": window.label, "start_equity": eq["start"], "end_equity": eq["current"],
        "peak_equity": eq["peak"], "low_equity": eq["low"], "max_drawdown_pct": eq["drawdown_pct"],
        "realized_pnl": eq["realized"], "unrealized_pnl": eq["unrealized"], "updated_at_ms": snapshot.time_ms})
    events = evaluate_behavior(snapshot, history_fills, cycles, eq, settings)
    inserted_events = store.save_risk_events(events)
    # Historical behavior remains available in the dashboard, but only a recent
    # event or a current-state risk may trigger an immediate Discord alert.
    active_events = [event for event in events if event["time_ms"] >= snapshot.time_ms - 10 * 60_000]
    legacy_risk = evaluate_risk(snapshot=snapshot, fills_today=fills_today, settings=settings)
    refresh_dashboard(settings, store, snapshot.time_ms, logger)
    if not active_events and not legacy_risk["flags"]:
        logger.info("即時リスク通知対象なし")
        return 0
    level = aggregate_level(active_events)
    if level == "GREEN" and legacy_risk["flags"]:
        level = "ORANGE" if legacy_risk["severity"] >= 20 else "YELLOW"
    message = format_behavior_risk_message(snapshot, active_events, eq, level) if active_events else format_risk_message(snapshot, legacy_risk)
    now_ms = int(datetime.now(JST).timestamp() * 1000)
    reason_key = "|".join(sorted(f"{e['risk_type']}:{e.get('coin') or '*'}" for e in active_events)) or legacy_risk["risk_key"]
    if not store.should_notify_risk(
        risk_key=reason_key,
        severity=LEVELS.get(level, 0) * 10,
        now_ms=now_ms,
        cooldown_minutes=settings.risk_cooldown_minutes,
    ):
        logger.info("同一リスクはクールダウン中のため通知スキップ")
        return 0

    send_discord_message(settings.discord_webhook_url, message, settings.dry_run, logger)
    store.record_risk_notification(reason_key, LEVELS.get(level, 0) * 10, now_ms, message)
    logger.info(f"risk events: total={len(events)}, active={len(active_events)}, new={inserted_events}, level={level}")
    return 0


def run_daily(settings: Settings, store: WalletStore, sample: bool, date_text: str | None, logger: object) -> int:
    now_jst = datetime.now(JST)
    window = daily_window(now_jst=now_jst, cutoff_hour=settings.daily_cutoff_hour_jst, date_text=date_text)
    payload, fills = fetch_payload(settings, sample=sample, start_ms=window.start_ms, end_ms=window.end_ms, logger=logger)
    snapshot = parse_snapshot(payload)
    parsed_fills = parse_fills(fills)
    store.save_snapshot(snapshot, payload)
    store.save_market_contexts(snapshot.time_ms, payload.get("market"))
    store.save_fills(parsed_fills)
    period_fills = store.fills_between(window.start_ms, window.end_ms)
    stats = build_period_stats(period_fills, snapshot)
    risk = evaluate_risk(snapshot=snapshot, fills_today=period_fills, settings=settings)
    score = score_daily(stats=stats, risk=risk, snapshot=snapshot)
    message = format_daily_report(window=window, snapshot=snapshot, stats=stats, risk=risk, score=score)
    report_path = settings.reports_dir / "daily" / f"{window.label}_daily_report.md"
    write_report(report_path, message)
    store.replace_trades(reconstruct_cycles(store.fills_between(0, window.end_ms)))
    refresh_dashboard(settings, store, snapshot.time_ms, logger)
    logger.info(f"daily report saved: {report_path}")
    send_discord_message(settings.discord_webhook_url, message, settings.dry_run, logger)
    return 0


def run_weekly(settings: Settings, store: WalletStore, sample: bool, date_text: str | None, logger: object) -> int:
    now_jst = datetime.now(JST)
    window = weekly_window(
        now_jst=now_jst,
        report_weekday=settings.weekly_weekday_jst,
        notify_hour=settings.weekly_notify_hour_jst,
        date_text=date_text,
    )
    payload, fills = fetch_payload(settings, sample=sample, start_ms=window.start_ms, end_ms=window.end_ms, logger=logger)
    snapshot = parse_snapshot(payload)
    parsed_fills = parse_fills(fills)
    store.save_snapshot(snapshot, payload)
    store.save_market_contexts(snapshot.time_ms, payload.get("market"))
    store.save_fills(parsed_fills)
    period_fills = store.fills_between(window.start_ms, window.end_ms)
    stats = build_period_stats(period_fills, snapshot)
    risk = evaluate_risk(snapshot=snapshot, fills_today=period_fills, settings=settings)
    score = score_weekly(stats=stats, risk=risk, snapshot=snapshot)
    message = format_weekly_report(window=window, snapshot=snapshot, stats=stats, risk=risk, score=score)
    report_path = settings.reports_dir / "weekly" / f"{window.label.replace('..', '_')}_weekly_report.md"
    write_report(report_path, message)
    store.replace_trades(reconstruct_cycles(store.fills_between(0, window.end_ms)))
    refresh_dashboard(settings, store, snapshot.time_ms, logger)
    logger.info(f"weekly report saved: {report_path}")
    send_discord_message(settings.discord_webhook_url, message, settings.dry_run, logger)
    return 0


def fetch_payload(
    settings: Settings,
    sample: bool,
    start_ms: int | None,
    end_ms: int | None,
    logger: object,
) -> tuple[dict, list[dict]]:
    if sample:
        return SAMPLE_SNAPSHOT, SAMPLE_FILLS

    client = HyperliquidClient(logger=logger)
    payload = client.fetch_wallet_snapshot(settings.wallet_address)
    if start_ms is not None and end_ms is not None:
        fills = client.user_fills_by_time(settings.wallet_address, start_ms=start_ms, end_ms=end_ms)
    else:
        fills = payload["fills"]
    return payload, fills


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
