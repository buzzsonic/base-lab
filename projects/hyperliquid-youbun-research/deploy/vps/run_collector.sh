#!/usr/bin/env bash
set -euo pipefail

data_repo="${DATA_REPO:-/data/repo}"
data_branch="${DATA_BRANCH:-data}"
timeout_seconds="${RUN_TIMEOUT_SECONDS:-1140}"
project="projects/hyperliquid-youbun-research"
output="$data_repo/$project/forward-data-v3"
lock_file="/runtime/youbun-forward-v3.lock"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p /runtime
exec 9>"$lock_file"
if ! flock -n 9; then
  printf '{"event":"skip","reason":"single_flight_lock","started_at":"%s"}\n' "$started_at"
  exit 0
fi

notify_failure() {
  local reason="$1"
  if [[ -n "${YOUBUN_DISCORD_WEBHOOK_URL:-}" ]]; then
    PYTHONPATH="$project" python "$project/scripts/notify_discord.py" \
      --status failure --work "forward-v3 collector" --tests "runtime quality gate" \
      --github "data branch" --next "collectorを停止して原因確認" --note "$reason" || true
  fi
}

if ! git -C "$data_repo" diff --quiet || ! git -C "$data_repo" diff --cached --quiet; then
  notify_failure "data checkout is dirty before collection"
  exit 20
fi
if ! git -C "$data_repo" push origin "HEAD:$data_branch"; then
  notify_failure "pending data commit push failed"
  exit 21
fi
if ! git -C "$data_repo" fetch origin "$data_branch" || ! git -C "$data_repo" merge --ff-only "origin/$data_branch"; then
  notify_failure "data branch fast-forward failed"
  exit 22
fi

args=()
if [[ -n "${MAX_WALLETS:-}" ]]; then args+=(--max-wallets "$MAX_WALLETS"); fi
set +e
PYTHONPATH="$project" timeout --signal=TERM --kill-after=30 "$timeout_seconds" \
  python "$project/scripts/forward_collect.py" \
  --sample "$project/sampling/pilot-100-v1/sampling_manifest.csv" \
  --output "$output" --collector-version forward-v3 "${args[@]}"
collector_status=$?
set -e

find "$output/raw" -type d -name '.run=*.tmp' -prune -exec rm -rf {} + 2>/dev/null || true
git -C "$data_repo" add -f "$project/forward-data-v3"
if ! git -C "$data_repo" diff --cached --quiet; then
  git -C "$data_repo" -c user.name='youbun-v3-collector' \
    -c user.email='youbun-v3-collector@users.noreply.github.com' \
    commit -m 'data: append Youbun forward v3 window'
  if ! (cd "$data_repo" && bash "/app/$project/scripts/push_data_branch.sh" "$data_branch" 3); then
    notify_failure "data branch push conflict"
    exit 23
  fi
fi

finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
latest_manifest="$(find "$output/raw" -name manifest.json -type f -print | sort | tail -1)"
if [[ -n "$latest_manifest" ]]; then
  python "$project/deploy/vps/status.py" --manifest "$latest_manifest" \
    --started-at "$started_at" --finished-at "$finished_at" --exit-code "$collector_status"
fi
if (( collector_status != 0 )); then
  reason="collector failed with exit $collector_status"
  if (( collector_status == 124 )); then reason="collector timeout; checkpoint unchanged"; fi
  notify_failure "$reason"
  exit "$collector_status"
fi
