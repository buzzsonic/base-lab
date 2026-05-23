from typing import Any


def build_position_report(
    snapshots: list[dict[str, Any]],
    previous_snapshot: dict[str, Any] | None,
    mids: dict[str, float],
    settings: Any,
) -> dict[str, Any]:
    current_positions = flatten_positions(snapshots=snapshots, mids=mids, settings=settings)
    previous_positions = previous_snapshot.get("positions", []) if previous_snapshot else []
    previous_by_key = {position_key(row): row for row in previous_positions if position_key(row)}

    current_report_positions = [
        row for row in current_positions if row["abs_position_usd"] >= settings.min_abs_position_usd
    ]
    new_positions: list[dict[str, Any]] = []
    increased_positions: list[dict[str, Any]] = []

    if previous_snapshot:
        for row in current_positions:
            key = position_key(row)
            previous = previous_by_key.get(key)
            if settings.target_side != "both" and row["side"] != settings.target_side:
                continue

            if previous is None:
                if row["abs_position_usd"] >= settings.min_position_change_usd:
                    new_positions.append({**row, "change_position_usd": row["abs_position_usd"], "change_size": row["abs_size"]})
                continue

            change = build_increase_row(current=row, previous=previous)
            if change and change["change_position_usd"] >= settings.min_position_change_usd:
                increased_positions.append(change)

    return {
        "has_previous_snapshot": previous_snapshot is not None,
        "current_positions": current_report_positions,
        "snapshot_positions": current_positions,
        "new_positions": new_positions,
        "increased_positions": increased_positions,
        "current_summary": aggregate_current_positions(current_report_positions),
        "new_summary": aggregate_change_positions(new_positions),
        "increased_summary": aggregate_change_positions(increased_positions),
        "stats": {
            "current_positions": len(current_report_positions),
            "new_positions": len(new_positions),
            "increased_positions": len(increased_positions),
            "raw_positions": len(current_positions),
        },
    }


def flatten_positions(snapshots: list[dict[str, Any]], mids: dict[str, float], settings: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for snapshot in snapshots:
        wallet = snapshot["wallet"]
        for position in snapshot.get("positions", []):
            if settings.target_side != "both" and position["side"] != settings.target_side:
                continue
            coin = position["coin"]
            current_px = mids.get(coin)
            rows.append(
                {
                    "address": wallet["address"],
                    "display_name": wallet.get("display_name"),
                    "rank": wallet.get("rank"),
                    "cohort": wallet["cohort"],
                    "cohort_label": wallet["cohort_label"],
                    "coin": coin,
                    "side": position["side"],
                    "size": position["size"],
                    "abs_size": position["abs_size"],
                    "entry_px": position["entry_px"],
                    "current_px": current_px,
                    "position_value_usd": position["position_value_usd"],
                    "abs_position_usd": resolve_position_usd(position=position, current_px=current_px),
                    "unrealized_pnl": position["unrealized_pnl"],
                    "liquidation_px": position["liquidation_px"],
                    "leverage_type": position["leverage_type"],
                    "leverage_value": position["leverage_value"],
                }
            )

    rows.sort(key=lambda row: row["abs_position_usd"], reverse=True)
    return rows


def build_increase_row(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any] | None:
    current_size = float(current.get("abs_size") or 0)
    previous_size = float(previous.get("abs_size") or 0)
    change_size = current_size - previous_size
    if change_size <= 0:
        return None

    current_px = current.get("current_px") or current.get("entry_px") or previous.get("entry_px")
    change_position_usd = change_size * float(current_px or 0)
    if change_position_usd <= 0:
        return None

    increase_entry_px = infer_increase_entry_px(current=current, previous=previous, change_size=change_size)
    return {
        **current,
        "entry_px": increase_entry_px or current.get("entry_px"),
        "change_size": change_size,
        "change_position_usd": change_position_usd,
        "previous_abs_size": previous_size,
        "previous_abs_position_usd": previous.get("abs_position_usd"),
    }


def infer_increase_entry_px(current: dict[str, Any], previous: dict[str, Any], change_size: float) -> float | None:
    current_entry = current.get("entry_px")
    previous_entry = previous.get("entry_px")
    current_size = current.get("abs_size")
    previous_size = previous.get("abs_size")
    if None in (current_entry, previous_entry, current_size, previous_size) or change_size <= 0:
        return None
    inferred = (float(current_entry) * float(current_size) - float(previous_entry) * float(previous_size)) / change_size
    if inferred <= 0:
        return None
    return inferred


def aggregate_current_positions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return aggregate_rows(rows=rows, value_key="abs_position_usd", size_key="abs_size")


def aggregate_change_positions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return aggregate_rows(rows=rows, value_key="change_position_usd", size_key="change_size")


def aggregate_rows(rows: list[dict[str, Any]], value_key: str, size_key: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["cohort"], row["coin"], row["side"])
        group = grouped.setdefault(
            key,
            {
                "cohort": row["cohort"],
                "cohort_label": row["cohort_label"],
                "coin": row["coin"],
                "side": row["side"],
                "total_usd": 0.0,
                "total_size": 0.0,
                "weighted_entry_sum": 0.0,
                "weighted_entry_size": 0.0,
                "unrealized_pnl": 0.0,
                "wallets": set(),
                "current_px": row.get("current_px"),
            },
        )
        value = float(row.get(value_key) or 0)
        size = float(row.get(size_key) or 0)
        entry_px = row.get("entry_px")
        group["total_usd"] += value
        group["total_size"] += size
        if entry_px is not None and size > 0:
            group["weighted_entry_sum"] += float(entry_px) * size
            group["weighted_entry_size"] += size
        if row.get("unrealized_pnl") is not None and value_key == "abs_position_usd":
            group["unrealized_pnl"] += float(row["unrealized_pnl"])
        group["wallets"].add(row["address"])

    summary: list[dict[str, Any]] = []
    for group in grouped.values():
        weighted_entry_size = group.pop("weighted_entry_size")
        weighted_entry_sum = group.pop("weighted_entry_sum")
        wallets = group.pop("wallets")
        group["avg_entry_px"] = weighted_entry_sum / weighted_entry_size if weighted_entry_size else None
        group["wallet_count"] = len(wallets)
        summary.append(group)

    summary.sort(key=lambda row: row["total_usd"], reverse=True)
    return summary


def resolve_position_usd(position: dict[str, Any], current_px: float | None) -> float:
    if current_px is not None:
        return abs(float(position.get("abs_size") or 0) * current_px)
    return float(position.get("abs_position_usd") or 0)


def position_key(row: dict[str, Any]) -> str | None:
    address = row.get("address")
    coin = row.get("coin")
    side = row.get("side")
    if not address or not coin or not side:
        return None
    return f"{address.lower()}|{coin}|{side}"
