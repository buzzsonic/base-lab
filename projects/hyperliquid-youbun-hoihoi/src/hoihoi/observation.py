from datetime import datetime, timedelta, timezone


def merge_observation(row, prior, now, config):
    row, prior = dict(row), prior or {}
    first = datetime.fromisoformat(prior.get('first_seen') or row['first_seen'])
    eligible = first + timedelta(days=config['observation_days'])
    row.update(first_seen=first.isoformat(), eligible_after=eligible.isoformat(), last_seen=now.isoformat())
    if 'poc_selected' in prior:
        row['poc_selected'] = prior['poc_selected']
    dates = set(prior.get('observation_dates') or [])
    if row['data_complete']:
        dates.add(now.astimezone(timezone(timedelta(hours=9))).date().isoformat())
    row.update(observation_dates=sorted(dates), successful_observation_days=len(dates))
    for field in ('discovery_source', 'discovery_detail'):
        if prior.get(field):
            row[field] = prior[field]
    flags = any(row.get(f) for f in ('bot_suspected', 'mm_suspected', 'farm_suspected', 'arbitrage_suspected', 'funding_arbitrage_suspected'))
    if flags:
        row['status'] = 'EXCLUDED'
    elif row['status'] != 'INACTIVE':
        row['status'] = ('ACTIVE' if now >= eligible and row['data_complete'] and len(dates) >= config.get('min_observation_days', 7) else 'OBSERVING')
    return row
