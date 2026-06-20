#!/usr/bin/env python3
"""
Fetch odds for Norway national team upcoming matches from The Odds API.
Converts bookmaker decimal odds → implied win probabilities (%).
Reads API key from env var ODDS_API_KEY.
Appends odds data to data/norway.json matches.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""

import json
import os
import urllib.request
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')

ODDS_KEY  = os.environ.get('ODDS_API_KEY', '')
BASE_URL  = 'https://api.the-odds-api.com/v4'
HEADERS   = {'User-Agent': 'ThorPost/1.0'}

# Soccer competitions where Norway national team might appear
COMPETITIONS = [
    'soccer_uefa_nations_league',
    'soccer_international_friendly',
    'soccer_fifa_world_cup_qualification_europe',
    'soccer_uefa_european_championship_qualification',
    'soccer_uefa_nations_league_b',
]


def api_get(path):
    url = f'{BASE_URL}{path}'
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=12)
            remaining = r.headers.get('x-requests-remaining', '?')
            print(f'  Requests remaining: {remaining}')
            if r.status_code == 422:
                return None   # sport not available right now
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f'  API error ({path[:60]}): {e}')
        return None


def get_available_sports():
    data = api_get(f'/sports/?apiKey={ODDS_KEY}')
    if not data:
        return []
    return [s['key'] for s in data if 'soccer' in s.get('key', '') and s.get('active')]


def odds_to_prob(outcomes):
    """
    Convert a list of {name, price} decimal odds to normalised probabilities.
    Returns dict: {team_name: probability_pct}
    """
    if not outcomes:
        return {}
    raw = {o['name']: 1.0 / o['price'] for o in outcomes if o.get('price', 0) > 0}
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {name: round(prob / total * 100, 1) for name, prob in raw.items()}


def average_probs(bookmakers):
    """Average win probabilities across all bookmakers for a match."""
    all_probs = {}
    count = {}
    for bm in bookmakers:
        for market in bm.get('markets', []):
            if market.get('key') != 'h2h':
                continue
            probs = odds_to_prob(market.get('outcomes', []))
            for team, pct in probs.items():
                all_probs[team] = all_probs.get(team, 0) + pct
                count[team] = count.get(team, 0) + 1
    if not all_probs:
        return {}
    return {team: round(all_probs[team] / count[team], 1) for team in all_probs}


def find_norway_odds():
    """
    Search available soccer competitions for a Norway match with odds.
    Returns list of match dicts with odds attached.
    """
    if not ODDS_KEY:
        print('  No ODDS_API_KEY — skipping odds')
        return []

    # First try known competitions, then discover from API
    sports_to_try = COMPETITIONS[:]
    discovered = get_available_sports()
    for s in discovered:
        if s not in sports_to_try:
            sports_to_try.append(s)

    norway_matches = []

    for sport in sports_to_try:
        print(f'  Checking {sport}...')
        events = api_get(
            f'/sports/{sport}/odds/'
            f'?apiKey={ODDS_KEY}&regions=eu&markets=h2h&dateFormat=iso&oddsFormat=decimal'
        )
        if not events:
            continue

        for event in events:
            home = event.get('home_team', '')
            away = event.get('away_team', '')
            if 'Norway' not in home and 'Norway' not in away:
                continue

            probs = average_probs(event.get('bookmakers', []))
            commence = event.get('commence_time', '')
            norway_matches.append({
                'date':        commence[:10],
                'time':        commence[11:16] if len(commence) > 15 else '',
                'home':        home,
                'away':        away,
                'competition': event.get('sport_title', sport),
                'venue':       '',
                'odds': {
                    'home_pct': probs.get(home),
                    'away_pct': probs.get(away),
                    'draw_pct': probs.get('Draw'),
                },
            })
            print(f'    Found: {home} vs {away} on {commence[:10]}')

        if norway_matches:
            break   # found matches, stop searching

    return sorted(norway_matches, key=lambda m: m['date'])


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    norway_path = os.path.join(DATA_DIR, 'norway.json')

    print('Fetching Norway odds from The Odds API...')
    odds_matches = find_norway_odds()
    print(f'  Found {len(odds_matches)} Norway match(es) with odds')

    # Load existing norway.json
    existing = {'updated': '', 'team': 'Herrelandslaget', 'matches': []}
    if os.path.exists(norway_path):
        try:
            with open(norway_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            pass

    if odds_matches:
        # Merge: prefer odds_matches (richer data), fall back to existing fixture list
        # Match by date + teams
        existing_by_key = {}
        for m in existing.get('matches', []):
            key = f"{m['date']}|{m['home']}|{m['away']}"
            existing_by_key[key] = m

        merged = []
        odds_keys = set()
        for m in odds_matches:
            key = f"{m['date']}|{m['home']}|{m['away']}"
            odds_keys.add(key)
            merged.append(m)

        # Add fixtures-only matches that aren't in odds (future season, no odds yet)
        for m in existing.get('matches', []):
            key = f"{m['date']}|{m['home']}|{m['away']}"
            if key not in odds_keys:
                merged.append(m)

        existing['matches'] = sorted(merged, key=lambda m: m['date'])
    # else: keep existing matches as-is (odds not available yet)

    existing['updated'] = datetime.utcnow().strftime('%Y-%m-%d')

    with open(norway_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f'Written: {norway_path}')


if __name__ == '__main__':
    main()
