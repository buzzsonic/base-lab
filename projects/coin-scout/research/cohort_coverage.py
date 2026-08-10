"""コホート収集の欠測を監視し、閾値割れをDiscordに通知する。

なぜ要るか(2026-08-10): cohort-snapshot は「毎時5分」の設定で全runがsuccessを返していたのに、
実際の時単位カバー率は52%しかなかった。**成功しているのに取れていない**ため、
ワークフローの成否だけを見ていると気づけない。データ側から見る監視をここで持つ。

使い方:
    python cohort_coverage.py --file data/cohorts.jsonl            # 表示のみ
    python cohort_coverage.py --file data/cohorts.jsonl --notify   # 閾値割れならDiscord通知
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.discord import send_discord_message  # noqa: E402

WINDOW_HOURS = 24
MIN_COVERAGE = 0.80   # 直近24hのうち8割の「時」が埋まっていなければ異常とみなす


class _Log:
    def info(self, m): print(m)
    def warning(self, m): print(m, file=sys.stderr)


def load_hours(path: Path) -> list[datetime]:
    hours = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                ts = datetime.fromisoformat(json.loads(line)["ts"])
            except (ValueError, KeyError, TypeError):
                continue
            hours.append(ts.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))
    return hours


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, required=True)
    ap.add_argument("--window", type=int, default=WINDOW_HOURS)
    ap.add_argument("--min-coverage", type=float, default=MIN_COVERAGE)
    ap.add_argument("--notify", action="store_true")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"エラー: {args.file} がありません", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    expected = [now - timedelta(hours=i) for i in range(1, args.window + 1)]
    have = set(load_hours(args.file))
    missing = [h for h in expected if h not in have]
    coverage = 1 - len(missing) / len(expected)

    latest = max(have) if have else None
    lag_h = (now - latest).total_seconds() / 3600 if latest else float("inf")

    print(f"直近{args.window}h のカバー率: {coverage:.0%} ({len(expected)-len(missing)}/{len(expected)})")
    print(f"最終記録: {latest:%Y-%m-%dT%H}Z (遅延 {lag_h:.0f}h)" if latest else "記録なし")
    if missing:
        print("欠測時刻: " + ", ".join(f"{h:%m-%d %H}Z" for h in sorted(missing)[:12])
              + (" ..." if len(missing) > 12 else ""))

    if coverage >= args.min_coverage:
        return 0

    message = (
        f"⚠️ コホート収集が欠測しています\n"
        f"直近{args.window}hのカバー率 **{coverage:.0%}** (基準 {args.min_coverage:.0%})\n"
        f"最終記録: {latest:%Y-%m-%d %H}Z / 欠測 {len(missing)}時間分\n"
        f"cohort-fade検証は等間隔サンプルが前提です。収集経路を確認してください。"
    )
    print("\n" + message)

    if args.notify:
        webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not webhook:
            print("DISCORD_WEBHOOK_URL が未設定のため通知しません", file=sys.stderr)
            return 1
        send_discord_message(webhook, message, dry_run=False, logger=_Log())
        print("Discord通知を送信しました")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
