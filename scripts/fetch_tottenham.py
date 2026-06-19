#!/usr/bin/env python3
"""
Fetch Tottenham Hotspur data from thesportsdb.com (free public API).
- Last 5 results
- Next fixture
- Premier League standings

Writes to data/tottenham.json
"""

import json
import os
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
import urllib.request

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')

# thesportsdb.com free public API
SPURS_ID    = '33576'
PL_ID       = '4328'   # English Premier League
API         = 'https://www.thesportsdb.com/api/v1/json/3'
HEADERS     = {'User-Agent': 'ThorPost/1.0 (personal news reader)'}

def fetch(url):
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  fetch failed: {e}')
        return None

def result_for_spurs(e):
    """Return W/D/L from Tottenham's perspective."""
    hs = e.get('intHomeScore')
    as_ = e.get('intAwayScore')
    if hs is None or as_ is None or hs == '' or as_ == '':
        return 'D'
    hs, as_ = int(hs), int(as_)
    is_home = 'Tottenham' in (e.get('strHomeTeam') or '')
    if hs == as_:
        return 'D'
    spurs_won = (is_home and hs > as_) or (not is_home and as_ > hs)
    return 'W' if spurs_won else 'L'

def get_recent_results():
    data = fetch(f'{API}/eventslast.php?id={SPURS_ID}')
    if not data or not data.get('results'):
        return []
    results = []
    for e in (data['results'] or [])[:5]:
        hs = e.get('intHomeScore')
        as_ = e.get('intAwayScore')
        comp = (e.get('strLeague') or '').replace('English Premier League', 'Premier League')
        results.append({
            'date':       e.get('dateEvent', ''),
            'home':       e.get('strHomeTeam', ''),
            'away':       e.get('strAwayTeam', ''),
            'home_score': hs,
            'away_score': as_,
            'competition': comp,
            'result':     result_for_spurs(e),
        })
    return results

def get_next_match():
    data = fetch(f'{API}/eventsnext.php?id={SPURS_ID}')
    if not data or not data.get('events'):
        return None
    e = data['events'][0]
    comp = (e.get('strLeague') or '').replace('English Premier League', 'Premier League')
    time_str = (e.get('strTime') or '')[:5]
    return {
        'date':        e.get('dateEvent', ''),
        'time':        time_str,
        'home':        e.get('strHomeTeam', ''),
        'away':        e.get('strAwayTeam', ''),
        'competition': comp,
        'venue':       e.get('strVenue', ''),
    }

def get_standings():
    """Fetch PL standings for current or most recent season."""
    now   = datetime.utcnow()
    year  = now.year
    month = now.month
    # PL season runs Aug–May
    if month >= 8:
        seasons = [f'{year}-{year+1}', f'{year-1}-{year}']
    else:
        seasons = [f'{year-1}-{year}', f'{year}-{year+1}']

    for season in seasons:
        data = fetch(f'{API}/lookuptable.php?l={PL_ID}&s={season}')
        if data and data.get('table'):
            table = []
            for row in data['table']:
                team = row.get('strTeam', '')
                table.append({
                    'pos':      _int(row.get('intRank')),
                    'team':     team,
                    'played':   _int(row.get('intPlayed')),
                    'won':      _int(row.get('intWin')),
                    'drawn':    _int(row.get('intDraw')),
                    'lost':     _int(row.get('intLoss')),
                    'gd':       _int(row.get('intGoalDifference')),
                    'points':   _int(row.get('intPoints')),
                    'is_spurs': 'Tottenham' in team,
                })
            print(f'  Standings for {season}: {len(table)} teams')
            return table, season
    return [], ''

def get_badge():
    data = fetch(f'{API}/lookupteam.php?id={SPURS_ID}')
    if data and data.get('teams'):
        return data['teams'][0].get('strTeamBadge', '') or ''
    return ''

def _int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')

    print('Fetching Tottenham recent results...')
    results = get_recent_results()
    print(f'  {len(results)} results')

    print('Fetching next Tottenham match...')
    next_match = get_next_match()
    print(f'  Next: {next_match}')

    print('Fetching PL standings...')
    standings, season = get_standings()

    print('Fetching team badge...')
    badge = get_badge()

    out = {
        'updated':        today,
        'season':         season,
        'badge_url':      badge,
        'recent_results': results,
        'next_match':     next_match,
        'standings':      standings,
    }

    path = os.path.join(DATA_DIR, 'tottenham.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path}')

if __name__ == '__main__':
    main()
