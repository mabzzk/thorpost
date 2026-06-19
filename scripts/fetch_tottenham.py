#!/usr/bin/env python3
"""
Fetch Tottenham Hotspur data:
  - Premier League standings  }  football-data.org (free API key required)
  - Last 5 results            }
  - Next fixture              }
  - Team badge                → thesportsdb.com (free, no key)

Reads API key from env var FOOTBALL_API_KEY.
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

FD_BASE    = 'https://api.football-data.org/v4'
FD_KEY     = os.environ.get('FOOTBALL_API_KEY', '')
SPURS_ID   = 73       # football-data.org Tottenham team ID
PL_CODE    = 'PL'

SDB_BASE   = 'https://www.thesportsdb.com/api/v1/json/3'
SDB_SPURS  = '33576'

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def fetch_fd(path):
    """Fetch from football-data.org with auth header."""
    url = f'{FD_BASE}{path}'
    headers = {
        'X-Auth-Token': FD_KEY,
        'User-Agent': 'ThorPost/1.0',
    }
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  football-data.org error ({path}): {e}')
        return None

def fetch_free(url):
    """Fetch from unauthenticated endpoint."""
    headers = {'User-Agent': 'ThorPost/1.0'}
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  fetch error ({url}): {e}')
        return None

# ── Standings ─────────────────────────────────────────────────────────────────
def get_standings():
    if not FD_KEY:
        print('  No FOOTBALL_API_KEY — skipping standings')
        return [], ''

    data = fetch_fd(f'/competitions/{PL_CODE}/standings')
    if not data:
        return [], ''

    season_obj = data.get('season', {})
    start = season_obj.get('startDate', '')[:4]
    end   = season_obj.get('endDate',   '')[:4]
    season = f'{start}-{end}' if start and end else ''

    for block in (data.get('standings') or []):
        if block.get('type') == 'TOTAL':
            table = []
            for row in block.get('table', []):
                team = row.get('team', {}).get('name', '')
                table.append({
                    'pos':      row.get('position', 0),
                    'team':     team,
                    'played':   row.get('playedGames', 0),
                    'won':      row.get('won', 0),
                    'drawn':    row.get('draw', 0),
                    'lost':     row.get('lost', 0),
                    'gd':       row.get('goalDifference', 0),
                    'points':   row.get('points', 0),
                    'is_spurs': 'Tottenham' in team or 'Spurs' in team,
                })
            print(f'  Standings: {len(table)} teams, season {season}')
            return table, season
    return [], season

# ── Matches ───────────────────────────────────────────────────────────────────
def parse_match(m):
    home  = m.get('homeTeam', {}).get('name', '')
    away  = m.get('awayTeam', {}).get('name', '')
    score = m.get('score', {})
    ft    = score.get('fullTime', {})
    hs, as_ = ft.get('home'), ft.get('away')
    date  = (m.get('utcDate') or '')[:10]
    comp  = m.get('competition', {}).get('name', '')

    result = 'D'
    if hs is not None and as_ is not None:
        is_home = 'Tottenham' in home or 'Spurs' in home
        if hs == as_:
            result = 'D'
        elif (is_home and hs > as_) or (not is_home and as_ > hs):
            result = 'W'
        else:
            result = 'L'

    return {
        'date':        date,
        'home':        home,
        'away':        away,
        'home_score':  hs,
        'away_score':  as_,
        'competition': comp.replace('Primera Division','La Liga'),
        'result':      result,
    }

def get_recent_results():
    if not FD_KEY:
        return []
    data = fetch_fd(f'/teams/{SPURS_ID}/matches?status=FINISHED&limit=5&competitions={PL_CODE}')
    if not data:
        # Try without competition filter (gets cups etc. too)
        data = fetch_fd(f'/teams/{SPURS_ID}/matches?status=FINISHED&limit=5')
    if not data or not data.get('matches'):
        return []
    matches = sorted(data['matches'], key=lambda x: x.get('utcDate',''), reverse=True)
    return [parse_match(m) for m in matches[:5]]

def get_next_match():
    if not FD_KEY:
        return None
    data = fetch_fd(f'/teams/{SPURS_ID}/matches?status=SCHEDULED&limit=1')
    if not data or not data.get('matches'):
        # Try TIMED status
        data = fetch_fd(f'/teams/{SPURS_ID}/matches?status=TIMED&limit=1')
    if not data or not data.get('matches'):
        return None
    m = data['matches'][0]
    date = (m.get('utcDate') or '')[:10]
    time = (m.get('utcDate') or '')[11:16]
    return {
        'date':        date,
        'time':        time,
        'home':        m.get('homeTeam', {}).get('name', ''),
        'away':        m.get('awayTeam', {}).get('name', ''),
        'competition': m.get('competition', {}).get('name', ''),
        'venue':       m.get('venue', ''),
    }

# ── Badge (thesportsdb, free) ─────────────────────────────────────────────────
def get_badge():
    data = fetch_free(f'{SDB_BASE}/lookupteam.php?id={SDB_SPURS}')
    if data and data.get('teams'):
        return data['teams'][0].get('strTeamBadge', '') or ''
    return ''

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')

    if not FD_KEY:
        print('WARNING: FOOTBALL_API_KEY not set. Standings and match data will be empty.')

    print('Fetching PL standings...')
    standings, season = get_standings()

    print('Fetching recent results...')
    results = get_recent_results()
    print(f'  {len(results)} results')

    print('Fetching next match...')
    next_match = get_next_match()
    print(f'  Next: {next_match}')

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
