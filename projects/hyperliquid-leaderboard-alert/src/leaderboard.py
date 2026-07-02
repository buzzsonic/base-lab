import html
import math
import re
import time
from typing import Any

import requests


DEXLY_URL = "https://dexly.trade/hyperliquid/leaderboard?window=month&sort=pnl&order={order}&limit={limit}&offset=0"
ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")


class LeaderboardError(RuntimeError):
    pass


def fetch_leaderboard_positions(client: Any, limit: int, logger: Any) -> list[dict[str, Any]]:
    wallets = fetch_leaderboard_wallets(limit=limit, logger=logger)
    if not wallets:
        raise LeaderboardError("リーダーボードからウォレットを取得できませんでした。")

    snapshots: list[dict[str, Any]] = []
    total = len(wallets)

    for index, wallet in enumerate(wallets, start=1):
        address = wallet["address"]
        logger.info(f"clearinghouseState取得 {index}/{total}: {wallet['cohort_label']} #{wallet['rank']} {short_address(address)}")
        try:
            state = client.clearinghouse_state(address)
            positions = extract_positions(state)
            snapshots.append({"wallet": wallet, "positions": positions, "error": None})
        except Exception as exc:
            logger.warning(f"ウォレット状態の取得に失敗: {short_address(address)} error={exc}")
            snapshots.append({"wallet": wallet, "positions": [], "error": str(exc)})
        time.sleep(0.05)

    return snapshots


def fetch_leaderboard_wallets(limit: int, logger: Any) -> list[dict[str, Any]]:
    cohorts = [
        {"cohort": "winner", "cohort_label": "勝ちウォレット", "order": "desc"},
        {"cohort": "loser", "cohort_label": "負けウォレット", "order": "asc"},
    ]
    wallets: list[dict[str, Any]] = []

    for cohort in cohorts:
        url = DEXLY_URL.format(order=cohort["order"], limit=limit)
        logger.info(f"Dexly公開リーダーボード取得: {cohort['cohort_label']} limit={limit}")
        page_text = _http_get(url)
        rows = _parse_dexly_rows(
            page_text=page_text,
            cohort=cohort["cohort"],
            cohort_label=cohort["cohort_label"],
            order=cohort["order"],
            limit=limit,
        )
        if not rows:
            raise LeaderboardError(f"{cohort['cohort_label']} のウォレットを解析できませんでした。")
        logger.info(f"{cohort['cohort_label']} {len(rows)}件を取得")
        wallets.extend(rows)

    return wallets


def extract_positions(state: dict[str, Any]) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    asset_positions = state.get("assetPositions", [])
    if not isinstance(asset_positions, list):
        return positions

    for item in asset_positions:
        position = item.get("position", {}) if isinstance(item, dict) else {}
        if not isinstance(position, dict):
            continue

        size = _to_float(position.get("szi"))
        if size is None or size == 0:
            continue

        entry_px = _to_float(position.get("entryPx"))
        position_value = _to_float(position.get("positionValue"))
        abs_position_usd = abs(position_value) if position_value is not None else None
        if abs_position_usd is None and entry_px is not None:
            abs_position_usd = abs(size) * entry_px

        leverage = position.get("leverage", {})
        if not isinstance(leverage, dict):
            leverage = {}

        positions.append(
            {
                "coin": position.get("coin", "UNKNOWN"),
                "side": "long" if size > 0 else "short",
                "size": size,
                "abs_size": abs(size),
                "entry_px": entry_px,
                "position_value_usd": position_value,
                "abs_position_usd": abs_position_usd or 0.0,
                "unrealized_pnl": _to_float(position.get("unrealizedPnl")),
                "liquidation_px": _to_float(position.get("liquidationPx")),
                "leverage_type": leverage.get("type"),
                "leverage_value": _to_float(leverage.get("value")),
            }
        )

    return positions


def _http_get(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "Accept": "text/html,application/json,*/*",
                "User-Agent": "base-lab-hyperliquid-leaderboard-alert/0.1",
            },
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise LeaderboardError(f"Dexly公開リーダーボード取得に失敗しました: {exc}") from exc


def _parse_dexly_rows(page_text: str, cohort: str, cohort_label: str, order: str, limit: int) -> list[dict[str, Any]]:
    normalized = html.unescape(page_text).replace('\\"', '"').replace("\\/", "/")
    pattern = re.compile(
        r'\{"ethAddress":"(?P<address>0x[a-fA-F0-9]{40})",'
        r'"displayName":(?P<displayName>null|".*?"),'
        r'"accountValue":(?P<accountValue>-?[0-9.eE]+|null),'
        r'"active24h":(?P<active24h>true|false|null),'
        r'"isHft":(?P<isHft>true|false|null),'
        r'"fillsPerMin":(?P<fillsPerMin>-?[0-9.eE]+|null),'
        r'"snapshotRank":(?P<snapshotRank>-?[0-9.eE]+|null),'
        r'"metrics":\{"pnl":(?P<pnl>-?[0-9.eE]+|null),'
        r'"roi":(?P<roi>-?[0-9.eE]+|null),'
        r'"vlm":(?P<vlm>-?[0-9.eE]+|null)\}\}',
    )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in pattern.finditer(normalized):
        data = match.groupdict()
        address = data["address"].lower()
        if address in seen:
            continue
        seen.add(address)
        rows.append(
            {
                "address": address,
                "display_name": _parse_display(data["displayName"]),
                "account_value": _to_float(data["accountValue"]),
                "active_24h": _parse_bool(data["active24h"]),
                "is_hft": _parse_bool(data["isHft"]),
                "fills_per_min": _to_float(data["fillsPerMin"]),
                "snapshot_rank": _to_float(data["snapshotRank"]),
                "pnl_30d": _to_float(data["pnl"]),
                "roi_30d": _to_float(data["roi"]),
                "volume_30d": _to_float(data["vlm"]),
                "source": "dexly_html_structured",
                "cohort": cohort,
                "cohort_label": cohort_label,
            }
        )

    if rows:
        reverse = order == "desc"
        # pnl欠損行は昇順/降順どちらでも末尾に落とす
        missing_key = -math.inf if reverse else math.inf
        rows.sort(key=lambda row: row["pnl_30d"] if row["pnl_30d"] is not None else missing_key, reverse=reverse)
    else:
        rows = _fallback_address_rows(normalized, cohort=cohort, cohort_label=cohort_label)

    for rank, row in enumerate(rows[:limit], start=1):
        row["rank"] = rank
    return rows[:limit]


def _fallback_address_rows(text: str, cohort: str, cohort_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in ADDRESS_PATTERN.finditer(text):
        address = match.group(0).lower()
        if address in seen:
            continue
        seen.add(address)
        rows.append(
            {
                "address": address,
                "display_name": None,
                "account_value": None,
                "active_24h": None,
                "is_hft": None,
                "fills_per_min": None,
                "snapshot_rank": None,
                "pnl_30d": None,
                "roi_30d": None,
                "volume_30d": None,
                "source": "dexly_html_address_fallback",
                "cohort": cohort,
                "cohort_label": cohort_label,
            }
        )
    return rows


def _to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_bool(value: Any) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _parse_display(raw: str | None) -> str | None:
    if raw in (None, "null", ""):
        return None
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw


def short_address(address: str) -> str:
    if len(address) <= 12:
        return address
    return f"{address[:6]}...{address[-4:]}"
