from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .reconstruct import attribute_funding, continuity_errors, quality_summary, reconstruct_episodes


INFO = "https://api.hyperliquid.xyz/info"
LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


def get_json(url: str, payload: dict | None = None, retries: int = 7):
    body = json.dumps(payload).encode() if payload else None
    headers = {"Accept": "application/json", "User-Agent": "youbun-research/0.1"}
    if body:
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, data=body, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            last = exc
            if attempt + 1 < retries:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(10 * (2 ** attempt), 120)
                time.sleep(wait)
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(min(3 * (2 ** attempt), 30))
    raise RuntimeError(f"request failed: {url}: {last}")


def select_accounts(rows: list[dict], limit: int) -> list[dict]:
    """Select active, non-whale-volume accounts across monthly ROI strata."""
    def metrics(row):
        windows = row.get("windowPerformances") or []
        values = {item[0]: item[1] for item in windows if isinstance(item, list) and len(item) == 2}
        perf = values.get("month") or values.get("allTime") or {}
        try:
            return {
                "pnl": float(perf.get("pnl", 0)), "roi": float(perf.get("roi", 0)),
                "volume": float(perf.get("vlm", 0)), "account_value": float(row.get("accountValue", 0)),
            }
        except (TypeError, ValueError):
            return {"pnl": 0.0, "roi": 0.0, "volume": 0.0, "account_value": 0.0}
    usable = []
    for row in rows:
        item = metrics(row)
        if row.get("ethAddress") and 100_000 <= item["volume"] <= 10_000_000 and item["account_value"] >= 100:
            usable.append((row, item))
    ordered = sorted(usable, key=lambda pair: pair[1]["roi"])
    if len(ordered) <= limit:
        chosen = ordered
    else:
        thirds = [limit // 3, limit // 3, limit - 2 * (limit // 3)]
        middle = ordered[len(ordered)//2 - thirds[1]//2:len(ordered)//2 - thirds[1]//2 + thirds[1]]
        chosen = ordered[:thirds[0]] + middle + ordered[-thirds[2]:]
    return [{"wallet": row["ethAddress"], **{f"selection_{key}": value for key, value in item.items()}}
            for row, item in chosen]


def _row_key(row: dict) -> str:
    tid = str(row.get("tid") or "")
    return tid or hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def fetch_fills(wallet: str, start_ms: int, end_ms: int, raw_dir: Path,
                page_delay_seconds: float = 4.0) -> list[dict]:
    cache = raw_dir / f"fills_{wallet.lower()}_{start_ms}_{end_ms}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    rows, seen, cursor = [], set(), start_ms
    for _ in range(100):
        batch = get_json(INFO, {"type": "userFillsByTime", "user": wallet, "startTime": cursor,
                                "endTime": end_ms, "aggregateByTime": False})
        added = 0
        for row in batch:
            key = _row_key(row)
            if key not in seen:
                seen.add(key)
                rows.append(row)
                added += 1
        if len(batch) < 2000:
            break
        next_cursor = max(int(row["time"]) for row in batch)
        if next_cursor < cursor or added == 0:
            raise RuntimeError(f"fills pagination stalled at {cursor}")
        cursor = next_cursor
        if cursor >= end_ms:
            break
        time.sleep(page_delay_seconds)
    cache.write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def fetch_twap_fills(wallet: str, start_ms: int, end_ms: int, raw_dir: Path) -> list[dict]:
    cache = raw_dir / f"twap_fills_{wallet.lower()}_{start_ms}_{end_ms}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    wrapped = get_json(INFO, {"type": "userTwapSliceFills", "user": wallet})
    rows = []
    for item in wrapped:
        fill = dict(item.get("fill") or {})
        if start_ms <= int(fill.get("time") or 0) <= end_ms:
            fill["twapId"] = item.get("twapId")
            rows.append(fill)
    cache.write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def fetch_funding(wallet: str, start_ms: int, end_ms: int, raw_dir: Path,
                  page_delay_seconds: float = 4.0) -> list[dict]:
    cache = raw_dir / f"funding_{wallet.lower()}_{start_ms}_{end_ms}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    rows, seen, cursor = [], set(), start_ms
    for _ in range(100):
        batch = get_json(INFO, {"type": "userFunding", "user": wallet,
                                "startTime": cursor, "endTime": end_ms})
        added = 0
        for row in batch:
            key = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                rows.append(row)
                added += 1
        if len(batch) < 500:
            break
        next_cursor = max(int(row["time"]) for row in batch)
        if next_cursor < cursor or added == 0:
            raise RuntimeError(f"funding pagination stalled at {cursor}")
        cursor = next_cursor
        if cursor >= end_ms:
            break
        time.sleep(page_delay_seconds)
    cache.write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def merge_fills(regular: list[dict], twap: list[dict]) -> tuple[list[dict], int]:
    """Merge omitted TWAP slices without double counting slices already in userFillsByTime."""
    out, seen, added = [], set(), 0
    for source, rows in (("regular", regular), ("twap", twap)):
        for row in rows:
            key = str(row.get("tid") or "") or f"{row.get('hash')}|{row.get('oid')}|{row.get('time')}|{row.get('sz')}"
            if key in seen:
                continue
            seen.add(key)
            copy = dict(row)
            copy["source_kind"] = source
            out.append(copy)
            added += source == "twap"
    return order_same_timestamp_by_position(out), added


def order_same_timestamp_by_position(rows: list[dict], tolerance: Decimal = Decimal("0.00000001")) -> list[dict]:
    """Interleave fills from separate endpoints using their observed position chain."""
    indexed_by_coin: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, row in enumerate(rows):
        indexed_by_coin[str(row.get("coin"))].append((index, row))
    ranked: list[tuple[int, int, dict]] = []
    for coin_rows in indexed_by_coin.values():
        by_time: dict[int, list[tuple[int, dict]]] = defaultdict(list)
        for index, row in coin_rows:
            by_time[int(row["time"])].append((index, row))
        expected: Decimal | None = None
        rank = 0
        for timestamp in sorted(by_time):
            remaining = list(by_time[timestamp])
            while remaining:
                matches = [item for item in remaining if expected is not None and
                           abs(Decimal(str(item[1].get("startPosition") or 0)) - expected) <= tolerance]
                if matches:
                    chosen = min(matches, key=lambda item: item[0])
                elif expected is None:
                    afters = []
                    for _, candidate in remaining:
                        qty = Decimal(str(candidate.get("sz") or 0))
                        before = Decimal(str(candidate.get("startPosition") or 0))
                        afters.append(before + (qty if candidate.get("side") == "B" else -qty))
                    heads = [item for item in remaining if not any(
                        abs(Decimal(str(item[1].get("startPosition") or 0)) - after) <= tolerance
                        for after in afters)]
                    chosen = min(heads or remaining, key=lambda item: item[0])
                else:
                    chosen = min(remaining, key=lambda item: item[0])
                remaining.remove(chosen)
                row = chosen[1]
                before = Decimal(str(row.get("startPosition") or 0))
                qty = Decimal(str(row.get("sz") or 0))
                expected = before + (qty if row.get("side") == "B" else -qty)
                ranked.append((timestamp, rank, row))
                rank += 1
    return [row for _, _, row in sorted(ranked, key=lambda item: (item[0], item[1]))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--end-ms", type=int, default=None, help="Pin the UTC end time for reproducible cache reuse")
    parser.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()
    raw_dir = args.output / "raw"
    processed_dir = args.output / "processed"
    quality_dir = args.output / "quality"
    for path in (raw_dir, processed_dir, quality_dir):
        path.mkdir(parents=True, exist_ok=True)

    leaderboard_cache = raw_dir / "leaderboard.json"
    if leaderboard_cache.exists():
        leaderboard = json.loads(leaderboard_cache.read_text())
    else:
        leaderboard = get_json(LEADERBOARD)
        leaderboard_cache.write_text(json.dumps(leaderboard, ensure_ascii=False))
    accounts = select_accounts(leaderboard.get("leaderboardRows", []), args.limit)
    end = (datetime.fromtimestamp(args.end_ms / 1000, timezone.utc)
           if args.end_ms is not None else datetime.now(timezone.utc))
    start = end - timedelta(days=args.days)
    all_rows, quality_rows = [], []
    for index, account in enumerate(accounts):
        cache = raw_dir / f"fills_{account['wallet'].lower()}_{int(start.timestamp()*1000)}_{int(end.timestamp()*1000)}.json"
        was_cached = cache.exists()
        start_ms, end_ms = int(start.timestamp()*1000), int(end.timestamp()*1000)
        fills = fetch_fills(account["wallet"], start_ms, end_ms, raw_dir)
        twap_fills = fetch_twap_fills(account["wallet"], start_ms, end_ms, raw_dir)
        funding_rows = fetch_funding(account["wallet"], start_ms, end_ms, raw_dir)
        merged_fills, twap_added = merge_fills(fills, twap_fills)
        # Spot pairs use @-prefixed identifiers and have different inventory/fee semantics.
        # This study's leverage/liquidation hypotheses are perp-only; preserve spot in raw, exclude from episodes.
        perp_fills = [row for row in merged_fills if not str(row.get("coin", "")).startswith("@")]
        episodes = reconstruct_episodes(account["wallet"], perp_fills)
        attribute_funding(episodes, funding_rows, end_ms)
        all_rows.extend(e.row() for e in episodes)
        summary = quality_summary(episodes) | account | {
            "fills": len(fills), "twap_rows": len(twap_fills), "twap_added": twap_added,
            "merged_fills": len(merged_fills), "perp_fills": len(perp_fills),
            "funding_rows": len(funding_rows),
            "continuity_errors": continuity_errors(perp_fills),
            "twap_endpoint_capped": len(twap_fills) >= 2000,
        }
        summary["eligible_for_behavior_analysis"] = (
            summary["completed_uncensored"] > 0
            and summary["perp_fills"] > 0
            and summary["quantity_mismatches"] == 0
            and summary["continuity_errors"] == 0
            and not summary["twap_endpoint_capped"]
        )
        quality_rows.append(summary)
        if index + 1 < len(accounts) and not was_cached:
            time.sleep(8.0)

    write_csv(processed_dir / "position_episodes.csv", all_rows)
    write_csv(quality_dir / "account_quality.csv", quality_rows)
    manifest = {"generated_at": end.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
                "accounts": len(accounts), "episodes": len(all_rows), "quality": quality_rows}
    (quality_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
