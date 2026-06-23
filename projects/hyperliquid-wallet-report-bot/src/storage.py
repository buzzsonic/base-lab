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
    return f"{fill.time_ms}|{fill.coin}|{fill.direction}|{fill.px:.12g}|{fill.sz:.12g}|{fill.closed_pnl:.12g}|{fill.fee:.12g}"

