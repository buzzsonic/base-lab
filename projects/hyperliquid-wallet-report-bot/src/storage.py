import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import AccountSnapshot, Fill


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time_ms INTEGER NOT NULL,
  account_value REAL NOT NULL,
  withdrawable REAL NOT NULL,
  total_ntl_pos REAL NOT NULL,
  total_margin_used REAL NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
  snapshot_id INTEGER NOT NULL,
  coin TEXT NOT NULL,
  side TEXT NOT NULL,
  szi REAL NOT NULL,
  entry_px REAL,
  mid_px REAL,
  unrealized_pnl REAL NOT NULL,
  roe_pct REAL,
  leverage_type TEXT,
  leverage_value REAL,
  liquidation_px REAL,
  liquidation_distance_pct REAL,
  margin_used REAL NOT NULL,
  position_value REAL NOT NULL,
  FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS fills (
  fill_key TEXT PRIMARY KEY,
  time_ms INTEGER NOT NULL,
  coin TEXT NOT NULL,
  direction TEXT NOT NULL,
  px REAL NOT NULL,
  sz REAL NOT NULL,
  closed_pnl REAL NOT NULL,
  fee REAL NOT NULL,
  liquidation INTEGER NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fills_time ON fills(time_ms);

CREATE TABLE IF NOT EXISTS risk_notifications (
  risk_key TEXT PRIMARY KEY,
  last_notified_ms INTEGER NOT NULL,
  last_severity REAL NOT NULL,
  last_message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
  trade_id TEXT PRIMARY KEY, coin TEXT NOT NULL, direction TEXT NOT NULL,
  opened_at INTEGER NOT NULL, closed_at INTEGER, initial_entry REAL NOT NULL,
  avg_entry REAL NOT NULL, max_position_notional REAL NOT NULL,
  max_position_size REAL NOT NULL, realized_pnl REAL NOT NULL, fees REAL NOT NULL,
  duration_minutes REAL, number_of_adds INTEGER NOT NULL,
  number_of_partial_closes INTEGER NOT NULL, mae REAL, mfe REAL,
  behavior_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_trades_closed ON trades(closed_at);

CREATE TABLE IF NOT EXISTS risk_events (
  event_key TEXT PRIMARY KEY, time_ms INTEGER NOT NULL, risk_type TEXT NOT NULL,
  coin TEXT, level TEXT NOT NULL, detail TEXT NOT NULL, metrics_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events(time_ms);

CREATE TABLE IF NOT EXISTS bot_state (
  key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_stats (
  day_jst TEXT PRIMARY KEY, start_equity REAL, end_equity REAL, peak_equity REAL,
  low_equity REAL, max_drawdown_pct REAL, realized_pnl REAL, unrealized_pnl REAL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS market_snapshots (
  time_ms INTEGER NOT NULL, coin TEXT NOT NULL, day_ntl_vlm REAL,
  PRIMARY KEY(time_ms, coin)
);
CREATE INDEX IF NOT EXISTS idx_market_coin_time ON market_snapshots(coin, time_ms);
"""


class WalletStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def save_snapshot(self, snapshot: AccountSnapshot, raw_payload: dict[str, Any]) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO snapshots (time_ms, account_value, withdrawable, total_ntl_pos, total_margin_used, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.time_ms,
                snapshot.account_value,
                snapshot.withdrawable,
                snapshot.total_ntl_pos,
                snapshot.total_margin_used,
                json.dumps(raw_payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        snapshot_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO positions (
              snapshot_id, coin, side, szi, entry_px, mid_px, unrealized_pnl, roe_pct, leverage_type,
              leverage_value, liquidation_px, liquidation_distance_pct, margin_used, position_value
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_id,
                    pos.coin,
                    pos.side,
                    pos.szi,
                    pos.entry_px,
                    pos.mid_px,
                    pos.unrealized_pnl,
                    pos.roe_pct,
                    pos.leverage_type,
                    pos.leverage_value,
                    pos.liquidation_px,
                    pos.liquidation_distance_pct,
                    pos.margin_used,
                    pos.position_value,
                )
                for pos in snapshot.positions
            ],
        )
        self.conn.commit()
        return snapshot_id

    def save_fills(self, fills: list[Fill]) -> int:
        before = self.conn.total_changes
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO fills (fill_key, time_ms, coin, direction, px, sz, closed_pnl, fee, liquidation, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    fill_key(fill),
                    fill.time_ms,
                    fill.coin,
                    fill.direction,
                    fill.px,
                    fill.sz,
                    fill.closed_pnl,
                    fill.fee,
                    1 if fill.liquidation else 0,
                    json.dumps(fill.raw, ensure_ascii=False, sort_keys=True),
                )
                for fill in fills
            ],
        )
        self.conn.commit()
        return self.conn.total_changes - before

    def save_market_contexts(self, time_ms: int, market: Any) -> int:
        if not isinstance(market, (list, tuple)) or len(market) != 2:
            return 0
        meta, contexts = market
        universe = meta.get("universe", []) if isinstance(meta, dict) else []
        rows = []
        for index, asset in enumerate(universe):
            if not isinstance(asset, dict) or index >= len(contexts) or not isinstance(contexts[index], dict):
                continue
            value = contexts[index].get("dayNtlVlm")
            try:
                volume = float(value) if value is not None else None
            except (TypeError, ValueError):
                volume = None
            rows.append((time_ms, str(asset.get("name") or ""), volume))
        before = self.conn.total_changes
        self.conn.executemany("INSERT OR IGNORE INTO market_snapshots(time_ms,coin,day_ntl_vlm) VALUES(?,?,?)", rows)
        self.conn.commit()
        return self.conn.total_changes - before

    def market_volume_near(self, coin: str, time_ms: int, tolerance_ms: int = 10 * 60_000) -> float | None:
        row = self.conn.execute(
            "SELECT day_ntl_vlm,time_ms FROM market_snapshots WHERE coin=? AND time_ms BETWEEN ? AND ? "
            "ORDER BY ABS(time_ms-?) LIMIT 1", (coin, time_ms - tolerance_ms, time_ms + tolerance_ms, time_ms)
        ).fetchone()
        return float(row["day_ntl_vlm"]) if row is not None and row["day_ntl_vlm"] is not None else None

    def fills_between(self, start_ms: int, end_ms: int) -> list[Fill]:
        rows = self.conn.execute(
            """
            SELECT * FROM fills
            WHERE time_ms >= ? AND time_ms < ?
            ORDER BY time_ms ASC
            """,
            (start_ms, end_ms),
        ).fetchall()
        return [
            Fill(
                coin=row["coin"],
                direction=row["direction"],
                px=float(row["px"]),
                sz=float(row["sz"]),
                closed_pnl=float(row["closed_pnl"]),
                fee=float(row["fee"]),
                time_ms=int(row["time_ms"]),
                liquidation=bool(row["liquidation"]),
                raw=json.loads(row["raw_json"]),
            )
            for row in rows
        ]

    def should_notify_risk(self, risk_key: str, severity: float, now_ms: int, cooldown_minutes: int) -> bool:
        row = self.conn.execute(
            "SELECT last_notified_ms, last_severity FROM risk_notifications WHERE risk_key = ?",
            (risk_key,),
        ).fetchone()
        if row is None:
            return True
        elapsed_ms = now_ms - int(row["last_notified_ms"])
        if elapsed_ms >= cooldown_minutes * 60_000:
            return True
        # Re-notify when risk materially worsens inside the cooldown window.
        return severity > float(row["last_severity"]) + 2

    def latest_snapshot_before(self, time_ms: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE time_ms <= ? ORDER BY time_ms DESC, id DESC LIMIT 1", (time_ms,)
        ).fetchone()

    def snapshot_range(self, start_ms: int, end_ms: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE time_ms >= ? AND time_ms <= ? ORDER BY time_ms, id", (start_ms, end_ms)
        ).fetchall()

    def daily_stats_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM daily_stats ORDER BY day_jst"
        ).fetchall()]

    def risk_event_rows(self, start_ms: int = 0) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM risk_events WHERE time_ms >= ? ORDER BY time_ms", (start_ms,)
        ).fetchall()]

    def all_snapshot_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM snapshots ORDER BY time_ms, id"
        ).fetchall()]

    def replace_trades(self, trades: list[dict[str, Any]]) -> None:
        self.conn.executemany(
            """
            INSERT INTO trades (trade_id, coin, direction, opened_at, closed_at, initial_entry, avg_entry,
              max_position_notional, max_position_size, realized_pnl, fees, duration_minutes,
              number_of_adds, number_of_partial_closes, mae, mfe, behavior_json)
            VALUES (:trade_id,:coin,:direction,:opened_at,:closed_at,:initial_entry,:avg_entry,
              :max_position_notional,:max_position_size,:realized_pnl,:fees,:duration_minutes,
              :number_of_adds,:number_of_partial_closes,:mae,:mfe,:behavior_json)
            ON CONFLICT(trade_id) DO UPDATE SET closed_at=excluded.closed_at, avg_entry=excluded.avg_entry,
              max_position_notional=excluded.max_position_notional, max_position_size=excluded.max_position_size,
              realized_pnl=excluded.realized_pnl, fees=excluded.fees, duration_minutes=excluded.duration_minutes,
              number_of_adds=excluded.number_of_adds, number_of_partial_closes=excluded.number_of_partial_closes,
              mae=excluded.mae, mfe=excluded.mfe, behavior_json=excluded.behavior_json
            """, trades,
        )
        self.conn.commit()

    def closed_trades(self, start_ms: int = 0) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM trades WHERE closed_at IS NOT NULL AND closed_at >= ? ORDER BY closed_at", (start_ms,)
        ).fetchall()]

    def save_risk_events(self, events: list[dict[str, Any]]) -> int:
        before = self.conn.total_changes
        self.conn.executemany(
            "INSERT OR IGNORE INTO risk_events(event_key,time_ms,risk_type,coin,level,detail,metrics_json) "
            "VALUES(:event_key,:time_ms,:risk_type,:coin,:level,:detail,:metrics_json)", events,
        )
        self.conn.commit()
        return self.conn.total_changes - before

    def update_daily_stats(self, row: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO daily_stats(day_jst,start_equity,end_equity,peak_equity,low_equity,max_drawdown_pct,
              realized_pnl,unrealized_pnl,updated_at_ms)
              VALUES(:day_jst,:start_equity,:end_equity,:peak_equity,:low_equity,:max_drawdown_pct,
              :realized_pnl,:unrealized_pnl,:updated_at_ms)
              ON CONFLICT(day_jst) DO UPDATE SET end_equity=excluded.end_equity,
              peak_equity=MAX(daily_stats.peak_equity,excluded.peak_equity),
              low_equity=MIN(daily_stats.low_equity,excluded.low_equity),
              max_drawdown_pct=MAX(daily_stats.max_drawdown_pct,excluded.max_drawdown_pct),
              realized_pnl=excluded.realized_pnl,unrealized_pnl=excluded.unrealized_pnl,
              updated_at_ms=excluded.updated_at_ms""", row,
        )
        self.conn.commit()

    def record_risk_notification(self, risk_key: str, severity: float, now_ms: int, message: str) -> None:
        self.conn.execute(
            """
            INSERT INTO risk_notifications (risk_key, last_notified_ms, last_severity, last_message)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(risk_key) DO UPDATE SET
              last_notified_ms=excluded.last_notified_ms,
              last_severity=excluded.last_severity,
              last_message=excluded.last_message
            """,
            (risk_key, now_ms, severity, message),
        )
        self.conn.commit()


def fill_key(fill: Fill) -> str:
    if fill.tid:
        return f"tid:{fill.tid}"
    raw_hash = str(fill.raw.get("hash") or "")
    if raw_hash and raw_hash != "0x" + "0" * 64:
        return f"hash:{raw_hash}:{fill.oid}:{fill.time_ms}:{fill.sz:.12g}"
    return f"{fill.time_ms}|{fill.coin}|{fill.direction}|{fill.px:.12g}|{fill.sz:.12g}|{fill.closed_pnl:.12g}|{fill.fee:.12g}"
