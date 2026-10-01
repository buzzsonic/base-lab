from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any


ZERO = Decimal("0")


def dec(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


@dataclass
class Episode:
    wallet: str
    coin: str
    direction: str
    first_entry_time: int
    last_exit_time: int | None
    average_entry: Decimal
    average_exit: Decimal | None
    initial_size: Decimal
    max_size: Decimal
    number_of_adds: int
    number_of_partial_exits: int
    realized_pnl: Decimal
    fees: Decimal
    funding: Decimal
    net_pnl: Decimal
    entry_qty: Decimal
    exit_qty: Decimal
    closed: bool
    left_censored: bool
    liquidation_observed: bool

    def row(self) -> dict[str, Any]:
        out = asdict(self)
        for key, value in tuple(out.items()):
            if isinstance(value, Decimal):
                out[key] = str(value)
        return out


def reconstruct_episodes(wallet: str, fills: list[dict[str, Any]]) -> list[Episode]:
    """Reconstruct per-coin position episodes while preserving API order for ties."""
    indexed = sorted(enumerate(fills), key=lambda pair: (int(pair[1]["time"]), pair[0]))
    states: dict[str, dict[str, Any]] = {}
    output: list[Episode] = []

    for _, fill in indexed:
        coin = str(fill["coin"])
        before = dec(fill.get("startPosition"))
        qty = dec(fill.get("sz"))
        signed = qty if fill.get("side") == "B" else -qty
        after = before + signed
        px = dec(fill.get("px"))
        fee = dec(fill.get("fee"))
        closed_pnl = dec(fill.get("closedPnl"))

        state = states.get(coin)
        if state is None:
            state = _new_state(wallet, coin, fill, before, after)
            states[coin] = state

        closing_qty, opening_qty = _split_quantities(before, after, qty)
        if closing_qty:
            state["exit_notional"] += closing_qty * px
            state["exit_qty"] += closing_qty
        if opening_qty and before * after >= 0:
            if state["entry_qty"]:
                state["adds"] += 1
            state["entry_notional"] += opening_qty * px
            state["entry_qty"] += opening_qty
        if before * after > 0 and abs(after) < abs(before) and after != ZERO:
            state["partial_exits"] += 1

        old_fraction = (closing_qty / qty) if qty else ZERO
        state["fees"] += fee * old_fraction if before * after < 0 else fee
        state["pnl"] += closed_pnl
        state["max_size"] = max(state["max_size"], abs(before), abs(after))
        state["liquidation"] = state["liquidation"] or "liquidat" in str(fill.get("dir", "")).lower()

        if after == ZERO or before * after < 0:
            output.append(_finish(state, int(fill["time"]), closed=True))
            states.pop(coin, None)
            if before * after < 0:
                next_state = _new_state(wallet, coin, fill, ZERO, after)
                next_state["entry_notional"] = opening_qty * px
                next_state["entry_qty"] = opening_qty
                next_state["fees"] = fee * (opening_qty / qty) if qty else ZERO
                states[coin] = next_state

    output.extend(_finish(state, None, closed=False) for state in states.values())
    return sorted(output, key=lambda episode: (episode.first_entry_time, episode.coin))


def _new_state(wallet: str, coin: str, fill: dict[str, Any], before: Decimal, after: Decimal) -> dict[str, Any]:
    left_censored = before != ZERO
    return {
        "wallet": wallet,
        "coin": coin,
        "direction": "LONG" if after > ZERO else "SHORT",
        "first": int(fill["time"]),
        "entry_notional": ZERO,
        "entry_qty": ZERO,
        "exit_notional": ZERO,
        "exit_qty": ZERO,
        "initial_size": abs(after) if before == ZERO else abs(before),
        "max_size": max(abs(before), abs(after)),
        "adds": 0,
        "partial_exits": 0,
        "pnl": ZERO,
        "fees": ZERO,
        "left_censored": left_censored,
        "liquidation": False,
    }


def _split_quantities(before: Decimal, after: Decimal, qty: Decimal) -> tuple[Decimal, Decimal]:
    if before == ZERO:
        return ZERO, qty
    if after == ZERO:
        return qty, ZERO
    if before * after < 0:
        return abs(before), abs(after)
    if abs(after) > abs(before):
        return ZERO, abs(after) - abs(before)
    return abs(before) - abs(after), ZERO


def _finish(state: dict[str, Any], exit_time: int | None, closed: bool) -> Episode:
    return Episode(
        wallet=state["wallet"], coin=state["coin"], direction=state["direction"],
        first_entry_time=state["first"], last_exit_time=exit_time,
        average_entry=(state["entry_notional"] / state["entry_qty"] if state["entry_qty"] else ZERO),
        average_exit=(state["exit_notional"] / state["exit_qty"] if state["exit_qty"] else None),
        initial_size=state["initial_size"], max_size=state["max_size"],
        number_of_adds=state["adds"], number_of_partial_exits=state["partial_exits"],
        realized_pnl=state["pnl"], fees=state["fees"], entry_qty=state["entry_qty"],
        funding=ZERO, net_pnl=state["pnl"] - state["fees"],
        exit_qty=state["exit_qty"], closed=closed, left_censored=state["left_censored"],
        liquidation_observed=state["liquidation"],
    )


def attribute_funding(episodes: list[Episode], funding_rows: list[dict[str, Any]], window_end_ms: int) -> None:
    """Assign exact funding cash flows by coin and observed episode interval."""
    by_coin: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
    for row in funding_rows:
        delta = row.get("delta") or {}
        coin = str(delta.get("coin") or "")
        if coin:
            by_coin[coin].append((int(row.get("time") or 0), dec(delta.get("usdc"))))
    for episode in episodes:
        end = episode.last_exit_time if episode.last_exit_time is not None else window_end_ms
        episode.funding = sum(
            (amount for time_ms, amount in by_coin.get(episode.coin, [])
             if episode.first_entry_time <= time_ms <= end),
            ZERO,
        )
        episode.net_pnl = episode.realized_pnl - episode.fees + episode.funding


def quality_summary(episodes: list[Episode]) -> dict[str, Any]:
    completed = [e for e in episodes if e.closed and not e.left_censored]
    mismatches = [e for e in completed if e.entry_qty != e.exit_qty]
    return {
        "episodes": len(episodes),
        "completed_uncensored": len(completed),
        "left_censored": sum(e.left_censored for e in episodes),
        "open_right_censored": sum(not e.closed for e in episodes),
        "quantity_mismatches": len(mismatches),
        "liquidations_observed": sum(e.liquidation_observed for e in episodes),
    }


def continuity_errors(fills: list[dict[str, Any]], tolerance: Decimal = Decimal("0.00000001")) -> int:
    """Count adjacent startPosition breaks per coin after stable time ordering."""
    by_coin: dict[str, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(fills):
        by_coin[str(row["coin"])].append((int(row["time"]), index, row))
    errors = 0
    for rows in by_coin.values():
        previous_after: Decimal | None = None
        for _, _, row in sorted(rows, key=lambda item: (item[0], item[1])):
            before = dec(row.get("startPosition"))
            if previous_after is not None and abs(before - previous_after) > tolerance:
                errors += 1
            qty = dec(row.get("sz"))
            previous_after = before + (qty if row.get("side") == "B" else -qty)
    return errors
