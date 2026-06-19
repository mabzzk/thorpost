#!/usr/bin/env python3
"""
Fetch Norway men's national football team upcoming fixtures.
Uses football-data.org API (same key as Tottenham).
Reads API key from env var FOOTBALL_API_KEY.
Writes to data/norway.json
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

FD_BASE     = 'https://api.football-data.org/v4'
FD_KEY      = os.environ.get('FOOTBALL_API_KEY', '')
# Norway men's national team ID on football-data.org
NORWAY_ID   = 779

HEADERS = {
    'X-Auth-Token': FD_KEY,
    'User-Agent': 'ThorPost/1.0',
}


def fetch_fd(path):
    url = f'{FD_BASE}{path}'
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 403:
                print(f'  403 Forbidden: competition may not be in free tier ({path})')
                return None
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  football-data.org error ({path}): {e}')
        return None


def get_upcoming_matches(limit=5):
    if not FD_KEY:
        print('  No FOOTBALL_API_KEY — skipping Norway fixtures')
        return []

    # Try SCHEDULED first, then TIMED
    for status in ('SCHEDULED', 'TIMED'):
        data = fetch_fd(f'/teams/{NORWAY_ID}/matches?status={status}&limit={limit}')
        if data and data.get('matches'):
            matches = sorted(data['matches'], key=lambda x: x.get('utcDate', ''))
            result = []
            for m in matches[:limit]:
                utc = m.get('utcDate', '')
                result.append({
                    'date':        utc[:10],
                    'time':        utc[11:16] if len(utc) > 15 else '',
                    'home':        m.get('homeTeam', {}).get('name', ''),
                    'away':        m.get('awayTeam', {}).get('name', ''),
                    'competition': m.get('competition', {}).get('name', ''),
                    'venue':       m.get('venue', '') or '',
                })
            return result

    return []


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')

    if not FD_KEY:
        print('WARNING: FOOTBALL_API_KEY not set. Norway fixtures will be empty.')

    print('Fetching Norway national team fixtures...')
    matches = get_upcoming_matches(limit=5)
    print(f'  Got {len(matches)} upcoming matches')
    for m in matches:
        print(f"    {m['date']} {m['home']} — {m['away']} ({m['competition']})")

    out = {
        'updated': today,
        'team':    'Herrelandslaget',
        'matches': matches,
    }
    path = os.path.join(DATA_DIR, 'norway.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path}')


if __name__ == '__main__':
    main()
