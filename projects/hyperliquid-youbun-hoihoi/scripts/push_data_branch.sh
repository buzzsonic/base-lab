#!/usr/bin/env bash
set -euo pipefail

branch="${1:-data}"
max_attempts="${2:-3}"

for ((attempt = 1; attempt <= max_attempts; attempt++)); do
  if git push origin "HEAD:${branch}"; then
    exit 0
  fi
  if ((attempt == max_attempts)); then
    break
  fi
  echo "data branch changed remotely; rebasing before retry ${attempt}/${max_attempts}" >&2
  git fetch origin "${branch}"
  git rebase "origin/${branch}"
done

echo "failed to push ${branch} after ${max_attempts} attempts" >&2
exit 1
