"""収集鮮度を市場方向と分離して表示する。欠測を異常なしにしない。"""


def collection_health(state, now_ms, settings):
    times = sorted({r["observed_at_ms"] for rows in state.get("history", {}).values()
                    for r in rows if isinstance(r.get("observed_at_ms"), int)
                    and (now_ms // 3_600_000 - 24) * 3_600_000 <= r["observed_at_ms"] <= now_ms})
    last = state.get("last_run_ms")
    age = (now_ms - last) / 60_000 if isinstance(last, (int, float)) and last <= now_ms else None
    threshold = settings.observation_interval_minutes + settings.comparison_tolerance_minutes
    # 完了済みのUTC時間枠24個。現在進行中の枠は分母/分子に含めない。
    current_hour = now_ms // 3_600_000
    covered = len({t // 3_600_000 for t in times if current_hour - 24 <= t // 3_600_000 < current_hour})
    status = "unknown" if age is None else ("delayed" if age > threshold else "fresh")
    return {"status": status, "age_minutes": age, "covered_hours": covered, "expected_hours": 24}


def health_text(health):
    if not health or health.get("status") == "unknown":
        return "⚠️ 短期収集の状態不明。短期変化の有無は判定できません"
    age = health["age_minutes"]
    label = "⚠️ 短期収集遅延" if health["status"] == "delayed" else "短期収集最終"
    return f"{label}: {age:.0f}分前 / 完了済み24時間枠の記録 {health['covered_hours']}/24（5分間隔の充足率ではありません）"
