#!/usr/bin/env python3
"""
Fetch Larvik Turn fixture data from fotball.no.
fotball.no is JavaScript-rendered, so we try several approaches:
  1. Look for embedded __NEXT_DATA__ JSON in the page HTML
  2. Try a direct API endpoint
  3. Fall back gracefully (keep existing matches if any)

Writes to data/football.json
"""

import json
import re
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
FIKS_ID  = 194
HEADERS  = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8',
}

def fetch(url, timeout=12):
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r.text
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f'  fetch failed {url}: {e}')
        return None

def try_next_data(html):
    """Parse fixtures from __NEXT_DATA__ embedded JSON."""
    matches = []
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
    if not m:
        return matches
    try:
        data = json.loads(m.group(1))
        props = data.get('props', {}).get('pageProps', {})

        # Try several known keys
        for key in ('fixtures', 'matches', 'kampprogram', 'upcomingMatches', 'schedule'):
            fixtures = props.get(key)
            if isinstance(fixtures, list):
                for f in fixtures[:10]:
                    match = parse_match_obj(f)
                    if match:
                        matches.append(match)
                if matches:
                    break

        # Deeper search
        if not matches:
            for val in props.values():
                if isinstance(val, dict):
                    for key2 in ('fixtures', 'matches', 'kampprogram'):
                        sub = val.get(key2)
                        if isinstance(sub, list):
                            for f in sub[:10]:
                                match = parse_match_obj(f)
                                if match:
                                    matches.append(match)
    except Exception as e:
        print(f'  __NEXT_DATA__ parse error: {e}')
    return matches

def parse_match_obj(f):
    """Try to extract a match from a dict with various key naming conventions."""
    if not isinstance(f, dict):
        return None
    date = (f.get('matchDateTime') or f.get('dato') or f.get('date') or
            f.get('matchDate') or f.get('startTime') or '')
    home = (f.get('homeTeamName') or f.get('hjemmelag') or
            (f.get('homeTeam') or {}).get('name') or '')
    away = (f.get('awayTeamName') or f.get('bortelag') or
            (f.get('awayTeam') or {}).get('name') or '')
    time = (f.get('matchTime') or f.get('tid') or '')
    venue = (f.get('stadiumName') or f.get('bane') or f.get('venue') or '')
    if date and (home or away):
        return {'date': str(date)[:10], 'time': str(time)[:5], 'home': home, 'away': away, 'venue': venue}
    return None

def try_static_scrape(html):
    """Try scraping match info from rendered HTML (works only if SSR'd)."""
    matches = []
    # Look for ISO date patterns near team names
    date_patterns = re.findall(
        r'(\d{4}-\d{2}-\d{2})[^<]{0,100}?([A-ZÆØÅ][a-zæøå\s]+)\s*[-–]\s*([A-ZÆØÅ][a-zæøå\s]+)',
        html
    )
    for dp in date_patterns[:8]:
        date, home, away = dp
        matches.append({'date': date, 'time': '', 'home': home.strip(), 'away': away.strip(), 'venue': ''})
    return matches

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    out_path  = os.path.join(DATA_DIR, 'football.json')

    # Load existing to preserve old matches if scraping fails
    existing_matches = []
    if os.path.exists(out_path):
        try:
            with open(out_path, 'r', encoding='utf-8') as f:
                existing_matches = json.load(f).get('matches', [])
        except Exception:
            pass

    url = f'https://www.fotball.no/fotballdata/lag/hjem/?fiksId={FIKS_ID}'
    print(f'Fetching {url}...')
    html = fetch(url)

    matches = []
    if html:
        matches = try_next_data(html)
        print(f'  __NEXT_DATA__: {len(matches)} matches')
        if not matches:
            matches = try_static_scrape(html)
            print(f'  static scrape: {len(matches)} matches')

    if not matches:
        print('  No matches found via scraping. Keeping existing data.')
        matches = existing_matches

    # Filter to upcoming only and sort
    upcoming = []
    for m in matches:
        try:
            d = datetime.strptime(m['date'][:10], '%Y-%m-%d')
            if d >= datetime.utcnow().replace(hour=0, minute=0, second=0):
                upcoming.append(m)
        except Exception:
            upcoming.append(m)
    upcoming.sort(key=lambda x: x.get('date', ''))

    out = {
        'updated': today_str,
        'team': 'Larvik Turn',
        'source': url,
        'note': 'Oppdateres daglig. Klikk lenken for fullstendig oversikt.',
        'matches': upcoming[:8],
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {out_path} ({len(upcoming)} upcoming matches)')

    if not upcoming:
        print()
        print('NOTE: fotball.no is JavaScript-rendered and scraping may not work.')
        print('For reliable fixture data, consider using Playwright:')
        print('  pip install playwright && playwright install chromium')
        print('  Then update this script to use playwright.sync_api')

if __name__ == '__main__':
    main()
