from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TITLES = {
    "success": "🧑‍🌾 養分くん研究 Codex作業完了\n\n✅ Status: SUCCESS",
    "warning": "🧑‍🌾 養分くん研究 Codex作業完了\n\n⚠️ Status: COMPLETED WITH NOTES",
    "failure": "🧑‍🌾 養分くん研究 Codex作業停止\n\n❌ Status: FAILED",
}


def build_message(status: str, work: str, tests: str, github: str, next_task: str, note: str = "") -> str:
    labels = [TITLES[status], f"作業:\n{work}", f"Tests:\n{tests}"]
    if note:
        labels.append(("注意" if status != "failure" else "原因") + f":\n{note}")
    labels.extend([
        f"GitHub:\n{github}",
        f"Next:\n{next_task}",
        'ChatGPT確認:\n「養分くんプロジェクトのGitHub最新状態を見て」',
    ])
    return "\n\n".join(labels)


def send(message: str, webhook: str, retries: int = 2) -> None:
    payload = json.dumps({"content": message}, ensure_ascii=False).encode()
    request = Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=15) as response:
                if response.status not in (200, 204):
                    raise RuntimeError(f"unexpected Discord status: {response.status}")
                return
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(3)
    if isinstance(last_error, HTTPError):
        detail = f"HTTP {last_error.code} {last_error.reason}"
    else:
        detail = type(last_error).__name__
    raise RuntimeError(f"Discord notification failed: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a post-push completion notification.")
    parser.add_argument("--status", choices=TITLES, required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--github", required=True)
    parser.add_argument("--next", dest="next_task", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    message = build_message(args.status, args.work, args.tests, args.github, args.next_task, args.note)
    if args.dry_run:
        print(message)
        return 0
    webhook = os.environ.get("YOUBUN_DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        print("YOUBUN_DISCORD_WEBHOOK_URL is not configured; notification not sent.", file=sys.stderr)
        return 2
    try:
        send(message, webhook)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Discord completion notification sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
