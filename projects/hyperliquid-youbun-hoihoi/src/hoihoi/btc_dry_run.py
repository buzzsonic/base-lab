from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .storage import read_parquet, write_json, write_parquet


ZERO = Decimal("0")
JST = timezone(timedelta(hours=9))
FLAG_FIELDS = {
    "bot_suspected": "BOT_SUSPECTED",
    "mm_suspected": "MM_SUSPECTED",
    "arbitrage_suspected": "ARBITRAGE_SUSPECTED",
    "funding_arbitrage_suspected": "FUNDING_ARBITRAGE_SUSPECTED",
    "farm_suspected": "FARM_SUSPECTED",
}


def dec(value) -> Decimal:
    return Decimal(str(value or "0"))


def analyze_btc_fills(fills: list[dict]) -> dict:
    btc = [row for row in fills if row.get("coin") == "BTC"]
    times = [int(row["time"]) for row in btc]
    ambiguous = sum(count - 1 for count in Counter(times).values() if count > 1)
    active_days = len({datetime.fromtimestamp(value / 1000, JST).date() for value in times})
    continuity_errors = 0
    previous_after = None
    completed = []
    state = None
    quantity_mismatches = 0
    event_counts = Counter()

    for row in btc:
        before, qty, px = dec(row.get("startPosition")), dec(row.get("sz")), dec(row.get("px"))
        after = before + (qty if row.get("side") == "B" else -qty)
        if previous_after is not None and before != previous_after:
            continuity_errors += 1
        previous_after = after
        if before == ZERO:
            event_counts["entry"] += 1
            state = {"entry_qty": qty, "exit_qty": ZERO, "initial_notional": abs(qty * px),
                     "avg_entry": px, "adverse_add": False}
        elif before * after < 0:
            event_counts["reversal"] += 1
            if state:
                state["exit_qty"] += abs(before)
                if state["entry_qty"] != state["exit_qty"]:
                    quantity_mismatches += 1
                completed.append(state)
            opening = abs(after)
            state = {"entry_qty": opening, "exit_qty": ZERO, "initial_notional": opening * px,
                     "avg_entry": px, "adverse_add": False}
        elif abs(after) > abs(before):
            event_counts["add"] += 1
            added = abs(after) - abs(before)
            if state:
                distance_bps = ((px / state["avg_entry"]) - 1) * Decimal("10000")
                adverse = distance_bps <= -5 if after > ZERO else distance_bps >= 5
                if added / abs(before) >= Decimal("0.05") and adverse:
                    state["adverse_add"] = True
                total = state["entry_qty"] + added
                state["avg_entry"] = (state["avg_entry"] * state["entry_qty"] + px * added) / total
                state["entry_qty"] = total
        else:
            reduced = abs(before) - abs(after)
            if after == ZERO:
                event_counts["close"] += 1
            else:
                event_counts["reduce"] += 1
            if state:
                state["exit_qty"] += reduced
            if after == ZERO and state:
                if state["entry_qty"] != state["exit_qty"]:
                    quantity_mismatches += 1
                completed.append(state)
                state = None

    evidence = len(completed)
    averaging = "UNAVAILABLE" if evidence < 3 or ambiguous else (
        "TRUE" if any(item["adverse_add"] for item in completed) else "FALSE"
    )
    size_surge = "UNAVAILABLE"
    if evidence >= 6 and not ambiguous:
        ratios = []
        for index in range(5, evidence):
            prior = sorted(item["initial_notional"] for item in completed[index - 5:index])
            median = prior[2]
            ratios.append(completed[index]["initial_notional"] / median if median else ZERO)
        size_surge = "TRUE" if any(value >= 2 for value in ratios) else "FALSE"
    return {
        "btc_fill_count": len(btc), "btc_active_days": active_days,
        "completed_btc_episodes": evidence, "ambiguous_same_ms_rows": ambiguous,
        "continuity_error_count": continuity_errors,
        "quantity_mismatch_count": quantity_mismatches,
        "entry_fill_count": event_counts["entry"], "add_fill_count": event_counts["add"],
        "reduce_fill_count": event_counts["reduce"], "close_fill_count": event_counts["close"],
        "reversal_fill_count": event_counts["reversal"],
        "high_price_chase_candidate": "UNAVAILABLE",
        "averaging_down_candidate": averaging, "size_surge_candidate": size_surge,
    }


def audit_cohort(path: Path, cohort_id: str) -> tuple[list[dict], dict]:
    registry = read_parquet(path / "wallet_registry.parquet")
    rows = []
    reason_counts = Counter()
    for wallet_row in registry:
        wallet = str(wallet_row["wallet"])
        checkpoint_path = path / "fill-checkpoints" / f"{wallet}.json"
        checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
        metrics = analyze_btc_fills(checkpoint.get("fills", []))
        reasons = []
        for field, reason in FLAG_FIELDS.items():
            if wallet_row.get(field):
                reasons.append(reason)
        if not checkpoint or not checkpoint.get("complete") or checkpoint.get("gaps"):
            reasons.append("INCOMPLETE_FILL_HISTORY")
        if int(wallet_row.get("successful_observation_days") or 0) < 7:
            reasons.append("OBSERVATION_DAYS_LT_7")
        if metrics["btc_active_days"] < 3:
            reasons.append("BTC_ACTIVE_DAYS_LT_3")
        if metrics["btc_fill_count"] < 20:
            reasons.append("BTC_FILLS_LT_20")
        if metrics["completed_btc_episodes"] < 5:
            reasons.append("BTC_EPISODES_LT_5")
        if metrics["ambiguous_same_ms_rows"]:
            reasons.append("AMBIGUOUS_SAME_MS_ORDER")
        if metrics["continuity_error_count"]:
            reasons.append("BTC_CONTINUITY_ERROR")
        if metrics["quantity_mismatch_count"]:
            reasons.append("BTC_QUANTITY_MISMATCH")
        # Hoihoi currently stores userFillsByTime only. Absence of TWAP evidence
        # is never interpreted as no TWAP activity.
        reasons.append("TWAP_EVIDENCE_UNAVAILABLE")
        reasons = sorted(set(reasons))
        reason_counts.update(reasons)
        rows.append({
            "cohort_id": cohort_id, "wallet": wallet,
            "selection_version": "btc-research-selection-v0.1.0-draft",
            "eligibility": "UNAVAILABLE" if "TWAP_EVIDENCE_UNAVAILABLE" in reasons else "EXCLUDED",
            "exclusion_reasons": ";".join(reasons),
            "successful_observation_days": int(wallet_row.get("successful_observation_days") or 0),
            **metrics,
        })
    summary = {
        "cohort_id": cohort_id, "wallets": len(rows), "handoff_eligible": 0,
        "twap_evidence_available": 0,
        "btc_fills_ge_20": sum(row["btc_fill_count"] >= 20 for row in rows),
        "btc_active_days_ge_3": sum(row["btc_active_days"] >= 3 for row in rows),
        "btc_episodes_ge_5": sum(row["completed_btc_episodes"] >= 5 for row in rows),
        "btc_activity_all_three": sum(
            row["btc_fill_count"] >= 20 and row["btc_active_days"] >= 3
            and row["completed_btc_episodes"] >= 5 for row in rows
        ),
        "same_ms_order_unambiguous": sum(row["ambiguous_same_ms_rows"] == 0 for row in rows),
        "reconstruction_quality_clear": sum(
            row["ambiguous_same_ms_rows"] == 0 and row["continuity_error_count"] == 0
            and row["quantity_mismatch_count"] == 0 for row in rows
        ),
        "preliminary_pass_excluding_observation_twap_and_market": sum(
            row["btc_fill_count"] >= 20 and row["btc_active_days"] >= 3
            and row["completed_btc_episodes"] >= 5
            and row["ambiguous_same_ms_rows"] == 0 and row["continuity_error_count"] == 0
            and row["quantity_mismatch_count"] == 0
            and "INCOMPLETE_FILL_HISTORY" not in row["exclusion_reasons"]
            and not any(reason in row["exclusion_reasons"] for reason in FLAG_FIELDS.values())
            for row in rows
        ),
        "profile_status_counts": {
            name: dict(sorted(Counter(row[name] for row in rows).items()))
            for name in ("high_price_chase_candidate", "averaging_down_candidate", "size_surge_candidate")
        },
        "reason_counts": dict(sorted(reason_counts.items())),
    }
    return rows, summary


def run_dry_run(current: Path, shadow: Path, output: Path) -> dict:
    current_rows, current_summary = audit_cohort(current, "current")
    shadow_rows, shadow_summary = audit_cohort(shadow, shadow.name)
    output.mkdir(parents=True, exist_ok=True)
    write_parquet(output / "selection_audit.parquet", current_rows + shadow_rows)
    report = {
        "schema_version": 1,
        "selection_version": "btc-research-selection-v0.1.0-draft",
        "status": "DRY_RUN_NO_HANDOFF",
        "decision": "HOLD",
        "current": current_summary,
        "shadow": shadow_summary,
        "limitations": [
            "No Hoihoi TWAP slice evidence is stored, so no wallet can enter the handoff sample.",
            "Checkpoint tie order is hash-derived; wallets with multiple BTC fills in one millisecond are ambiguous.",
            "High-price-chase remains UNAVAILABLE because past-only BTC market windows were not joined.",
            "No PnL, outcome, or post-entry price field was used.",
        ],
    }
    write_json(output / "summary.json", report)
    return report
