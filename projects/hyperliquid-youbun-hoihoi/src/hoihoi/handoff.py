from __future__ import annotations

import re
from typing import Any


SCHEMA_VERSION = "hoihoi-btc-handoff-v0.1"
PROFILE_STATUSES = {"TRUE", "FALSE", "UNAVAILABLE"}
PROFILE_NAMES = {
    "high_price_chase_candidate",
    "averaging_down_candidate",
    "size_surge_candidate",
}
FORBIDDEN_OUTCOME_FIELDS = {
    "closedpnl",
    "net_pnl",
    "pnl",
    "profit_factor",
    "roi",
    "win_rate",
    "return_after_entry",
    "markout",
    "mfe",
    "mae",
    "future_return",
}
FORBIDDEN_OUTCOME_FRAGMENTS = (
    "pnl", "profit_factor", "win_rate", "roi", "markout", "future_return",
    "return_after_entry", "post_entry_return", "mfe", "mae",
)


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _is_outcome_key(key: str) -> bool:
    return key in FORBIDDEN_OUTCOME_FIELDS or any(fragment in key for fragment in FORBIDDEN_OUTCOME_FRAGMENTS)


def validate_handoff(payload: dict) -> list[str]:
    """Fail-closed checks used before a Hoihoi sample can reach Youbun research."""
    errors: list[str] = []
    required = {
        "schema_version", "selection_version", "profile_version", "sample_version",
        "generated_at", "observation_window", "source_snapshot", "wallets",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(f"missing top-level fields: {','.join(missing)}")
        return errors
    if payload["schema_version"] != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    window = payload.get("observation_window") or {}
    if int(window.get("successful_jst_days", 0)) < 7:
        errors.append("successful_jst_days must be at least 7")
    forbidden = sorted({key for key in _walk_keys(payload) if _is_outcome_key(key)})
    if forbidden:
        errors.append(f"outcome fields are forbidden: {','.join(forbidden)}")
    wallets = payload.get("wallets")
    if not isinstance(wallets, list):
        return errors + ["wallets must be a list"]
    seen_wallets: set[str] = set()
    seen_episodes: set[str] = set()
    for index, row in enumerate(wallets):
        prefix = f"wallets[{index}]"
        wallet = str(row.get("wallet", ""))
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", wallet):
            errors.append(f"{prefix}.wallet is invalid")
        if wallet.lower() in seen_wallets:
            errors.append(f"{prefix}.wallet is duplicated")
        seen_wallets.add(wallet.lower())
        if row.get("eligibility") != "ELIGIBLE" or row.get("exclusion_reasons") != []:
            errors.append(f"{prefix} is not an eligible-only handoff row")
        quality = row.get("quality") or {}
        if quality.get("data_complete") is not True:
            errors.append(f"{prefix}.quality.data_complete must be true")
        for name in ("unresolved_gap_count", "continuity_error_count", "quantity_mismatch_count"):
            if quality.get(name) != 0:
                errors.append(f"{prefix}.quality.{name} must be zero")
        if quality.get("twap_capped") is not False:
            errors.append(f"{prefix}.quality.twap_capped must be false")
        activity = row.get("btc_activity") or {}
        for name, minimum in (("active_days", 3), ("fill_count", 20), ("completed_episode_count", 5)):
            if int(activity.get(name, 0)) < minimum:
                errors.append(f"{prefix}.btc_activity.{name} must be at least {minimum}")
        profiles = row.get("behavior_profile") or {}
        if set(profiles) != PROFILE_NAMES:
            errors.append(f"{prefix}.behavior_profile names do not match the contract")
        for name, profile in profiles.items():
            if profile.get("status") not in PROFILE_STATUSES:
                errors.append(f"{prefix}.behavior_profile.{name}.status is invalid")
            if profile.get("status") == "UNAVAILABLE" and int(profile.get("evidence_episodes", 0)) != 0:
                errors.append(f"{prefix}.behavior_profile.{name} UNAVAILABLE must have zero evidence")
            if profile.get("status") in {"TRUE", "FALSE"} and int(profile.get("evidence_episodes", 0)) < 3:
                errors.append(f"{prefix}.behavior_profile.{name} requires at least 3 evidence episodes")
        episodes = row.get("episodes") or []
        if len(episodes) < 5:
            errors.append(f"{prefix}.episodes must contain at least 5 complete BTC episodes")
        if int(activity.get("completed_episode_count", -1)) != len(episodes):
            errors.append(f"{prefix}.completed_episode_count must equal episode rows")
        for episode in episodes:
            episode_id = str(episode.get("episode_id", ""))
            if not episode_id or episode_id in seen_episodes:
                errors.append(f"{prefix} contains a blank or duplicate episode_id")
            seen_episodes.add(episode_id)
            if episode.get("reconstruction_status") != "COMPLETE":
                errors.append(f"{prefix}.{episode_id} is not completely reconstructed")
            if int(episode.get("last_exit_time_ms", 0)) <= int(episode.get("first_entry_time_ms", 0)):
                errors.append(f"{prefix}.{episode_id} has an invalid time window")
    return errors
