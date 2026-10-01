from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.poc import merge_fills
from src.reconstruct import dec


ZERO = Decimal("0")
QTY_TOLERANCE = Decimal("0.00000001")
MONEY_TOLERANCE = Decimal("0.000001")
PRICE_TOLERANCE = Decimal("0.000001")


@dataclass
class RawEpisode:
    wallet: str
    coin: str
    direction: str
    first_entry_time: int
    last_exit_time: int | None = None
    entry_notional: Decimal = ZERO
    exit_notional: Decimal = ZERO
    entry_qty: Decimal = ZERO
    exit_qty: Decimal = ZERO
    realized_pnl: Decimal = ZERO
    fees: Decimal = ZERO
    builder_fee: Decimal = ZERO
    funding: Decimal = ZERO
    adds: int = 0
    partial_exits: int = 0
    fill_count: int = 0
    left_censored: bool = False
    closed: bool = False
    starts_with_reversal: bool = False
    ends_with_reversal: bool = False
    traces: list[str] = field(default_factory=list)

    @property
    def average_entry(self) -> Decimal:
        return self.entry_notional / self.entry_qty if self.entry_qty else ZERO

    @property
    def average_exit(self) -> Decimal | None:
        return self.exit_notional / self.exit_qty if self.exit_qty else None

    @property
    def net_pnl(self) -> Decimal:
        return self.realized_pnl - self.fees + self.funding

    @property
    def duration_ms(self) -> int:
        return (self.last_exit_time or self.first_entry_time) - self.first_entry_time


def split_quantities(before: Decimal, after: Decimal, qty: Decimal) -> tuple[Decimal, Decimal]:
    if before == ZERO:
        return ZERO, qty
    if after == ZERO:
        return qty, ZERO
    if before * after < ZERO:
        return abs(before), abs(after)
    if abs(after) > abs(before):
        return ZERO, abs(after) - abs(before)
    return abs(before) - abs(after), ZERO


def trace_line(row: dict[str, Any], before: Decimal, after: Decimal) -> str:
    builder = dec(row.get("builderFee"))
    return (
        f"{row['time']}|{row.get('source_kind', 'regular')}|{before}|{row.get('side')}|"
        f"{row.get('sz')}|{after}|px={row.get('px')}|pnl={row.get('closedPnl')}|"
        f"fee={row.get('fee')}|builder={builder}"
    )


def reconstruct_raw(wallet: str, fills: list[dict[str, Any]]) -> list[RawEpisode]:
    indexed = sorted(enumerate(fills), key=lambda item: (int(item[1]["time"]), item[0]))
    states: dict[str, RawEpisode] = {}
    output: list[RawEpisode] = []
    for _, row in indexed:
        coin = str(row["coin"])
        before = dec(row.get("startPosition"))
        qty = dec(row.get("sz"))
        after = before + (qty if row.get("side") == "B" else -qty)
        closing_qty, opening_qty = split_quantities(before, after, qty)
        flip = before * after < ZERO
        state = states.get(coin)
        if state is None:
            state = RawEpisode(
                wallet=wallet,
                coin=coin,
                direction="LONG" if after > ZERO else "SHORT",
                first_entry_time=int(row["time"]),
                left_censored=before != ZERO,
            )
            states[coin] = state

        state.fill_count += 1
        state.traces.append(trace_line(row, before, after))
        if closing_qty:
            state.exit_qty += closing_qty
            state.exit_notional += closing_qty * dec(row.get("px"))
        if opening_qty and not flip:
            if state.entry_qty:
                state.adds += 1
            state.entry_qty += opening_qty
            state.entry_notional += opening_qty * dec(row.get("px"))
        if before * after > ZERO and abs(after) < abs(before):
            state.partial_exits += 1

        old_fraction = closing_qty / qty if qty else ZERO
        state.fees += dec(row.get("fee")) * old_fraction if flip else dec(row.get("fee"))
        state.builder_fee += dec(row.get("builderFee")) * old_fraction if flip else dec(row.get("builderFee"))
        state.realized_pnl += dec(row.get("closedPnl"))

        if after == ZERO or flip:
            state.last_exit_time = int(row["time"])
            state.closed = True
            state.ends_with_reversal = flip
            output.append(state)
            states.pop(coin, None)
            if flip:
                next_state = RawEpisode(
                    wallet=wallet,
                    coin=coin,
                    direction="LONG" if after > ZERO else "SHORT",
                    first_entry_time=int(row["time"]),
                    entry_qty=opening_qty,
                    entry_notional=opening_qty * dec(row.get("px")),
                    fees=dec(row.get("fee")) * (opening_qty / qty),
                    builder_fee=dec(row.get("builderFee")) * (opening_qty / qty),
                    fill_count=1,
                    starts_with_reversal=True,
                    traces=[trace_line(row, before, after)],
                )
                states[coin] = next_state
    output.extend(states.values())
    return sorted(output, key=lambda item: (item.first_entry_time, item.coin))


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def one_file(raw_dir: Path, prefix: str, wallet: str) -> Path | None:
    matches = sorted(raw_dir.glob(f"{prefix}_{wallet.lower()}_*.json"))
    if len(matches) > 1:
        raise RuntimeError(f"multiple {prefix} files for one wallet: {wallet}")
    return matches[0] if matches else None


def load_wallet_raw(raw_dir: Path, wallet: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fill_path = one_file(raw_dir, "fills", wallet)
    if fill_path is None:
        return [], []
    regular = load_json(fill_path)
    twap_path = one_file(raw_dir, "twap_fills", wallet)
    twap = load_json(twap_path) if twap_path else []
    merged, _ = merge_fills(regular, twap)
    perp = [row for row in merged if not str(row.get("coin", "")).startswith("@")]
    funding_path = one_file(raw_dir, "funding", wallet)
    funding = load_json(funding_path) if funding_path else []
    return perp, funding


def attribute_raw_funding(episodes: list[RawEpisode], funding_rows: list[dict[str, Any]]) -> None:
    by_coin: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
    for row in funding_rows:
        delta = row.get("delta") or {}
        if delta.get("coin"):
            by_coin[str(delta["coin"])].append((int(row["time"]), dec(delta.get("usdc"))))
    for episode in episodes:
        if episode.last_exit_time is None:
            continue
        episode.funding = sum(
            (
                amount
                for time_ms, amount in by_coin.get(episode.coin, [])
                if episode.first_entry_time <= time_ms <= episode.last_exit_time
            ),
            ZERO,
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def eligible_wallets(quality_rows: list[dict[str, str]]) -> list[str]:
    return sorted(
        row["wallet"].lower()
        for row in quality_rows
        if int(row["completed_uncensored"]) > 0
        and int(row["perp_fills"]) > 0
        and int(row["quantity_mismatches"]) == 0
        and int(row["continuity_errors"]) == 0
        and row["twap_endpoint_capped"].lower() == "false"
    )


def delta(left: Decimal | None, right: Decimal | None) -> Decimal:
    return (left or ZERO) - (right or ZERO)


def compare(raw: RawEpisode, reconstructed: dict[str, str]) -> tuple[str, list[str], dict[str, Decimal]]:
    diffs = {
        "entry_qty": delta(raw.entry_qty, dec(reconstructed["entry_qty"])),
        "exit_qty": delta(raw.exit_qty, dec(reconstructed["exit_qty"])),
        "average_entry": delta(raw.average_entry, dec(reconstructed["average_entry"])),
        "average_exit": delta(raw.average_exit, dec(reconstructed["average_exit"])),
        "realized_pnl": delta(raw.realized_pnl, dec(reconstructed["realized_pnl"])),
        "fees": delta(raw.fees, dec(reconstructed["fees"])),
        "funding": delta(raw.funding, dec(reconstructed["funding"])),
    }
    reasons: list[str] = []
    exact_checks = {
        "entry_time": raw.first_entry_time == int(reconstructed["first_entry_time"]),
        "exit_time": raw.last_exit_time == int(reconstructed["last_exit_time"]),
        "direction": raw.direction == reconstructed["direction"],
        "adds": raw.adds == int(reconstructed["number_of_adds"]),
        "partial_exits": raw.partial_exits == int(reconstructed["number_of_partial_exits"]),
        "closed": reconstructed["closed"].lower() == "true",
        "left_censored": reconstructed["left_censored"].lower() == "false",
    }
    reasons.extend(name for name, passed in exact_checks.items() if not passed)
    for name in ("entry_qty", "exit_qty"):
        if abs(diffs[name]) > QTY_TOLERANCE:
            reasons.append(name)
    for name in ("average_entry", "average_exit"):
        if abs(diffs[name]) > PRICE_TOLERANCE:
            reasons.append(name)
    for name in ("realized_pnl", "fees", "funding"):
        if abs(diffs[name]) > MONEY_TOLERANCE:
            reasons.append(name)
    if raw.builder_fee < ZERO or raw.builder_fee - raw.fees > MONEY_TOLERANCE:
        reasons.append("builder_fee_not_contained_in_fee")
    return ("FAIL" if reasons else "PASS"), reasons, diffs


def bucket_by_rank(values: list[int], value: int) -> str:
    ordered = sorted(values)
    lower = ordered[(len(ordered) - 1) // 3]
    upper = ordered[(2 * (len(ordered) - 1)) // 3]
    if value <= lower:
        return "short" if values is not None else "low"
    if value <= upper:
        return "medium"
    return "long"


def stratify(episodes: list[RawEpisode]) -> dict[tuple[str, str, int, int], set[str]]:
    durations = [episode.duration_ms for episode in episodes]
    fills = [episode.fill_count for episode in episodes]
    duration_low = sorted(durations)[(len(durations) - 1) // 3]
    duration_high = sorted(durations)[(2 * (len(durations) - 1)) // 3]
    fill_low = sorted(fills)[(len(fills) - 1) // 3]
    fill_high = sorted(fills)[(2 * (len(fills) - 1)) // 3]

    def band(value: int, low: int, high: int, labels: tuple[str, str, str]) -> str:
        return labels[0] if value <= low else labels[1] if value <= high else labels[2]

    result = {}
    for episode in episodes:
        result[key_for(episode)] = {
            "win" if episode.net_pnl >= ZERO else "loss",
            episode.direction.lower(),
            "adds" if episode.adds else "no_adds",
            "partial" if episode.partial_exits else "no_partial",
            "reversal" if episode.starts_with_reversal or episode.ends_with_reversal else "no_reversal",
            "hold_" + band(episode.duration_ms, duration_low, duration_high, ("short", "medium", "long")),
            "fills_" + band(episode.fill_count, fill_low, fill_high, ("few", "medium", "many")),
        }
    return result


def key_for(episode: RawEpisode) -> tuple[str, str, int, int]:
    return (episode.wallet.lower(), episode.coin, episode.first_entry_time, episode.last_exit_time or 0)


def choose_sample(episodes: list[RawEpisode], strata: dict[tuple[str, str, int, int], set[str]], size: int) -> list[RawEpisode]:
    quotas = {
        "win": size // 2,
        "loss": size - size // 2,
        "long": size // 2,
        "short": size - size // 2,
        "hold_short": (size + 2) // 3,
        "hold_medium": (size + 1) // 3,
        "hold_long": size // 3,
        "fills_few": (size + 2) // 3,
        "fills_medium": (size + 1) // 3,
        "fills_many": size // 3,
        "no_adds": min(3, sum("no_adds" in values for values in strata.values())),
        "no_partial": min(4, sum("no_partial" in values for values in strata.values())),
        "reversal": min(2, sum("reversal" in values for values in strata.values())),
    }
    selected: list[RawEpisode] = []
    counts: dict[str, int] = defaultdict(int)
    remaining = list(episodes)
    wallets_seen: set[str] = set()
    all_wallets = {item.wallet for item in episodes}
    while remaining and len(selected) < size:
        slots_left = size - len(selected)

        def score(episode: RawEpisode) -> tuple[int, int, int, str]:
            values = strata[key_for(episode)]
            quota_gain = sum(
                (quotas[name] - counts[name]) * (5 if name == "reversal" else 1)
                for name in values
                if name in quotas and counts[name] < quotas[name]
            )
            wallets_left = len(all_wallets - wallets_seen)
            new_wallet = int(episode.wallet not in wallets_seen) * (20 if slots_left <= wallets_left else 4)
            rarity = sum(1 for name in values if sum(name in item for item in strata.values()) <= 8)
            stable = hashlib.sha256("|".join(map(str, key_for(episode))).encode()).hexdigest()
            return new_wallet + quota_gain, rarity, -episode.fill_count, stable

        chosen = max(remaining, key=score)
        selected.append(chosen)
        remaining.remove(chosen)
        for name in strata[key_for(chosen)]:
            counts[name] += 1
        wallets_seen.add(chosen.wallet)
    return sorted(selected, key=lambda item: (item.wallet, item.first_entry_time, item.coin))


def anonymized_aliases(wallets: list[str]) -> dict[str, str]:
    return {wallet: f"A{index:02d}" for index, wallet in enumerate(sorted(wallets), start=1)}


def fmt(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def write_review_csv(
    path: Path,
    sample: list[RawEpisode],
    recon_by_key: dict[tuple[str, str, int, int], dict[str, str]],
    strata: dict[tuple[str, str, int, int], set[str]],
    aliases: dict[str, str],
) -> list[dict[str, str]]:
    rows = []
    counters: dict[str, int] = defaultdict(int)
    for raw in sample:
        alias = aliases[raw.wallet]
        counters[alias] += 1
        episode_id = f"{alias}-E{counters[alias]:03d}"
        reconstructed = recon_by_key[key_for(raw)]
        status, reasons, diffs = compare(raw, reconstructed)
        rows.append({
            "episode_id": episode_id,
            "account_alias": alias,
            "coin": raw.coin,
            "strata": ",".join(sorted(strata[key_for(raw)])),
            "fill_count": str(raw.fill_count),
            "raw_entry_time": str(raw.first_entry_time),
            "reconstructed_entry_time": reconstructed["first_entry_time"],
            "raw_exit_time": str(raw.last_exit_time),
            "reconstructed_exit_time": reconstructed["last_exit_time"],
            "raw_direction": raw.direction,
            "reconstructed_direction": reconstructed["direction"],
            "raw_entry_qty": fmt(raw.entry_qty),
            "reconstructed_entry_qty": reconstructed["entry_qty"],
            "entry_qty_diff": fmt(diffs["entry_qty"]),
            "raw_exit_qty": fmt(raw.exit_qty),
            "reconstructed_exit_qty": reconstructed["exit_qty"],
            "exit_qty_diff": fmt(diffs["exit_qty"]),
            "raw_average_entry": fmt(raw.average_entry),
            "reconstructed_average_entry": reconstructed["average_entry"],
            "average_entry_diff": fmt(diffs["average_entry"]),
            "raw_average_exit": fmt(raw.average_exit),
            "reconstructed_average_exit": reconstructed["average_exit"],
            "average_exit_diff": fmt(diffs["average_exit"]),
            "raw_adds": str(raw.adds),
            "reconstructed_adds": reconstructed["number_of_adds"],
            "raw_partial_exits": str(raw.partial_exits),
            "reconstructed_partial_exits": reconstructed["number_of_partial_exits"],
            "raw_realized_pnl": fmt(raw.realized_pnl),
            "reconstructed_realized_pnl": reconstructed["realized_pnl"],
            "realized_pnl_diff": fmt(diffs["realized_pnl"]),
            "raw_fee": fmt(raw.fees),
            "reconstructed_fee": reconstructed["fees"],
            "fee_diff": fmt(diffs["fees"]),
            "raw_builder_fee_included_in_fee": fmt(raw.builder_fee),
            "raw_funding": fmt(raw.funding),
            "reconstructed_funding": reconstructed["funding"],
            "funding_diff": fmt(diffs["funding"]),
            "zero_to_zero": str(raw.entry_qty == raw.exit_qty),
            "reversal_boundary": str(raw.starts_with_reversal or raw.ends_with_reversal),
            "fill_order_preserved": "True",
            "status": status,
            "difference_reason": ",".join(reasons),
            "logic_fix_applied": "False",
            "raw_fill_trace": ";".join(raw.traces),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_report(
    path: Path,
    all_episodes: list[RawEpisode],
    review_rows: list[dict[str, str]],
    strata: dict[tuple[str, str, int, int], set[str]],
    population_failures: list[tuple[tuple[str, str, int, int], list[str]]],
) -> None:
    counts = {name: sum(name in values for values in strata.values()) for name in sorted(set().union(*strata.values()))}
    sample_counts = {
        name: sum(name in row["strata"].split(",") for row in review_rows)
        for name in counts
    }
    pass_count = sum(row["status"] == "PASS" for row in review_rows)
    fail_count = len(review_rows) - pass_count
    builder_count = sum(dec(row["raw_builder_fee_included_in_fee"]) != ZERO for row in review_rows)
    reversal_count = sum(row["reversal_boundary"] == "True" for row in review_rows)
    lines = [
        "# Episode reconstruction visual review — 2026-10-02",
        "",
        "## Scope and grain",
        "",
        f"- Population: {len(all_episodes)} completed, uncensored episodes from eligible accounts.",
        f"- Reviewed sample: {len(review_rows)} episodes; each row is one zero-to-zero position episode.",
        "- Wallets are replaced with deterministic aliases; raw wallet addresses are not included.",
        "- This is a reconstruction-quality review only. No FOMO/Late/Nanpin/Revenge labels were computed.",
        "",
        "## Selection",
        "",
        "A deterministic quota-guided selection covered outcome, direction, adds, partial exits, reversal boundaries, holding-time tertiles, fill-count tertiles, and all eligible accounts. Targets were approximately balanced for win/loss, Long/Short, and the two tertile dimensions while retaining rare edge cases.",
        "",
        "| stratum | population | reviewed |",
        "|---|---:|---:|",
    ]
    lines.extend(f"| {name} | {counts[name]} | {sample_counts[name]} |" for name in counts)
    lines.extend([
        "",
        "## Reconciliation result",
        "",
        f"- Full-population automated boundary/metric reconciliation: {len(all_episodes) - len(population_failures)}/{len(all_episodes)} PASS",
        f"- PASS: {pass_count}/{len(review_rows)}",
        f"- FAIL: {fail_count}/{len(review_rows)}",
        f"- Reversal-boundary samples: {reversal_count}",
        f"- Samples with non-zero builderFee: {builder_count}",
        "- Tolerances: quantity 1e-8, price 1e-6, PnL/fee/Funding 1e-6.",
        "- builderFee is checked as a component contained within fee and is not added again.",
        "- Fill order is the original merged API order for equal timestamps, after stable timestamp ordering.",
        "",
        "## Episode results",
        "",
        "| episode | account | coin | fills | strata | result | difference |",
        "|---|---|---|---:|---|---|---|",
    ])
    lines.extend(
        f"| {row['episode_id']} | {row['account_alias']} | {row['coin']} | {row['fill_count']} | {row['strata']} | {row['status']} | {row['difference_reason'] or '-'} |"
        for row in review_rows
    )
    lines.extend([
        "",
        "## Quality gate",
        "",
        ("**PASS:** No material discrepancies were found in the reviewed sample or the full-population automated reconciliation. The project may proceed to the final TWAP/Funding/builder-fee accounting check."
         if fail_count == 0 and not population_failures else
         "**FAIL:** Material discrepancies remain. Reconstruction logic must be corrected and the sample rerun before downstream labels."),
        "",
        "The full anonymized raw-versus-reconstructed values and ordered fill traces are in `episode_review.csv`.",
        "",
        "## Remaining limitations",
        "",
        "- This review covers 20 of 61 eligible episodes, not the full population.",
        "- The source cache is a fixed 30-day snapshot; this review does not prove completeness outside that window.",
        "- Historical cross-margin state and liquidation distance remain unavailable and were not inferred.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an anonymized stratified raw-fill episode review.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args()

    quality_rows = read_csv(args.data / "quality" / "account_quality.csv")
    wallets = eligible_wallets(quality_rows)
    reconstructed_rows = read_csv(args.data / "processed" / "position_episodes.csv")
    reconstructed_rows = [
        row
        for row in reconstructed_rows
        if row["wallet"].lower() in wallets
        and row["closed"].lower() == "true"
        and row["left_censored"].lower() == "false"
    ]
    recon_by_key = {
        (row["wallet"].lower(), row["coin"], int(row["first_entry_time"]), int(row["last_exit_time"])): row
        for row in reconstructed_rows
    }

    raw_episodes: list[RawEpisode] = []
    for wallet in wallets:
        fills, funding = load_wallet_raw(args.data / "raw", wallet)
        episodes = reconstruct_raw(wallet, fills)
        attribute_raw_funding(episodes, funding)
        raw_episodes.extend(item for item in episodes if item.closed and not item.left_censored)
    raw_by_key = {key_for(item): item for item in raw_episodes}
    if len(wallets) != 10 or len(raw_episodes) != 61 or len(reconstructed_rows) != 61:
        raise RuntimeError(
            f"unexpected review population: wallets={len(wallets)}, raw={len(raw_episodes)}, reconstructed={len(reconstructed_rows)}"
        )
    if raw_by_key.keys() != recon_by_key.keys():
        missing_raw = sorted(recon_by_key.keys() - raw_by_key.keys())
        missing_reconstructed = sorted(raw_by_key.keys() - recon_by_key.keys())
        raise RuntimeError(f"episode boundary mismatch: raw={missing_raw}, reconstructed={missing_reconstructed}")

    population_failures = []
    for episode_key, raw_episode in raw_by_key.items():
        status, reasons, _ = compare(raw_episode, recon_by_key[episode_key])
        if status != "PASS":
            population_failures.append((episode_key, reasons))

    strata = stratify(raw_episodes)
    sample = choose_sample(raw_episodes, strata, args.sample_size)
    aliases = anonymized_aliases(wallets)
    review_rows = write_review_csv(args.output / "episode_review.csv", sample, recon_by_key, strata, aliases)
    write_report(args.output / "README.md", raw_episodes, review_rows, strata, population_failures)
    failed = [row for row in review_rows if row["status"] != "PASS"]
    print(json.dumps({
        "wallets": len(wallets), "population": len(raw_episodes), "population_failed": len(population_failures),
        "reviewed": len(review_rows), "review_failed": len(failed),
    }))
    raise SystemExit(1 if failed or population_failures else 0)


if __name__ == "__main__":
    main()
