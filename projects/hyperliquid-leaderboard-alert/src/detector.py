from typing import Any


def detect_alerts(snapshots: list[dict[str, Any]], settings: Any) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    for snapshot in snapshots:
        wallet = snapshot["wallet"]
        for position in snapshot.get("positions", []):
            if settings.target_side != "both" and position["side"] != settings.target_side:
                continue
            if position["abs_position_usd"] < settings.min_abs_position_usd:
                continue

            alerts.append(
                {
                    "wallet": wallet,
                    "coin": position["coin"],
                    "side": position["side"],
                    "size": position["size"],
                    "abs_size": position["abs_size"],
                    "entry_px": position["entry_px"],
                    "position_value_usd": position["position_value_usd"],
                    "abs_position_usd": position["abs_position_usd"],
                    "unrealized_pnl": position["unrealized_pnl"],
                    "liquidation_px": position["liquidation_px"],
                    "leverage_type": position["leverage_type"],
                    "leverage_value": position["leverage_value"],
                }
            )

    alerts.sort(key=lambda row: row["abs_position_usd"], reverse=True)
    return alerts
