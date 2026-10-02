from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from .api import INFO_URL


def identity(fill):
    return hashlib.sha256(json.dumps(fill, sort_keys=True).encode()).hexdigest()


def collect_fills(api, wallet, path: Path, start_ms, end_ms, max_requests=100):
    prior = json.loads(path.read_text()) if path.exists() else {}
    if prior and end_ms < prior['checked_through']:
        raise ValueError('checkpoint cannot move backwards')
    start = max(start_ms, prior.get('checked_through', start_ms))
    stack, gathered, gaps, requests, capped = [(start, end_ms)], [], [], 0, 0
    while stack:
        lo, hi = stack.pop()
        if requests >= max_requests:
            gaps.append([lo, hi])
            continue
        batch = api.get_json(INFO_URL, {'type': 'userFillsByTime', 'user': wallet,
            'startTime': lo, 'endTime': hi, 'aggregateByTime': False})
        if not isinstance(batch, list):
            raise ValueError('invalid fills response')
        requests += 1
        if len(batch) >= 2000:
            capped += 1
            if lo == hi:
                gathered.extend(batch)
                gaps.append([lo, hi])
            else:
                mid = (lo + hi) // 2
                stack.extend([(mid + 1, hi), (lo, mid)])
        else:
            gathered.extend(batch)
    by_id = {identity(f): f for f in prior.get('fills', []) + gathered if start_ms <= int(f['time']) <= end_ms}
    fills = sorted(by_id.values(), key=lambda f: (int(f['time']), identity(f)))
    retention_risk = len({identity(f) for f in gathered}) >= 10000
    old_gaps = [g for g in prior.get('gaps', []) if g[1] >= start_ms]
    if retention_risk:
        gaps.append([start, end_ms])
    value = {'wallet': wallet, 'coverage_start': prior.get('coverage_start', start_ms),
        'checked_through': end_ms, 'fills': fills, 'gaps': old_gaps + gaps,
        'requests': requests, 'capped_responses': capped, 'retention_risk': retention_risk,
        'complete': not (old_gaps or gaps)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    os.replace(temporary, path)
    return value
