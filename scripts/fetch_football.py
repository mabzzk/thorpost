#!/usr/bin/env python3
"""
Fetch Larvik Turn fixture data from fotball.no using Playwright (headless browser).
Falls back to requests if Playwright is not available.
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

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
FIKS_ID  = 194
URL      = f'https://www.fotball.no/fotballdata/lag/hjem/?fiksId={FIKS_ID}'

# ── Playwright (primary) ──────────────────────────────────────────────────────
def fetch_with_playwright():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until='networkidle', timeout=30000)
        # Give JS-rendered content a moment
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return html

# ── requests fallback ─────────────────────────────────────────────────────────
def fetch_with_requests():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    if HAS_REQUESTS:
        r = requests.get(URL, headers=headers, timeout=12)
        r.raise_for_status()
        return r.text
    import urllib.request
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_next_data(html):
    """Try __NEXT_DATA__ embedded JSON first."""
    matches = []
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
    if not m:
        return matches
    try:
        data = json.loads(m.group(1))
        props = data.get('props', {}).get('pageProps', {})
        for key in ('fixtures', 'matches', 'kampprogram', 'upcomingMatches', 'schedule', 'kamper'):
            items = props.get(key)
            if isinstance(items, list):
                for f in items[:10]:
                    match = _parse_match(f)
                    if match:
                        matches.append(match)
                if matches:
                    return matches
        # Deeper search one level
        for val in props.values():
            if isinstance(val, dict):
                for key2 in ('fixtures', 'matches', 'kampprogram', 'kamper'):
                    sub = val.get(key2)
                    if isinstance(sub, list):
                        for f in sub[:10]:
                            match = _parse_match(f)
                            if match:
                                matches.append(match)
    except Exception as e:
        print(f'  __NEXT_DATA__ parse error: {e}')
    return matches

def parse_beautifulsoup(html):
    """Parse rendered HTML with BeautifulSoup."""
    matches = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Look for table rows that contain match info
        for row in soup.select('tr, [class*="match"], [class*="kamp"], [class*="fixture"]'):
            text = row.get_text(' ', strip=True)

            # Try to extract a date
            date_m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
            if not date_m:
                date_m = re.search(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', text)
                if date_m:
                    d, mo, y = date_m.groups()
                    date_str = f'{y}-{mo.zfill(2)}-{d.zfill(2)}'
                else:
                    continue
            else:
                date_str = date_m.group(1)

            # Try to find time
            time_m = re.search(r'\b(\d{2}:\d{2})\b', text)
            time_str = time_m.group(1) if time_m else ''

            # Try to find teams (X - Y or X – Y pattern)
            teams_m = re.search(
                r'([A-ZÆØÅ][A-Za-zÆØÅæøå\s\-\.]{2,40}?)\s*[-–]\s*([A-ZÆØÅ][A-Za-zÆØÅæøå\s\-\.]{2,40})',
                text
            )
            if teams_m:
                home, away = teams_m.group(1).strip(), teams_m.group(2).strip()
                matches.append({'date': date_str, 'time': time_str, 'home': home, 'away': away, 'venue': ''})

    except ImportError:
        print('  BeautifulSoup not available for HTML parsing')
    except Exception as e:
        print(f'  BeautifulSoup parse error: {e}')
    return matches

def _parse_match(f):
    if not isinstance(f, dict):
        return None
    date  = (f.get('matchDateTime') or f.get('dato') or f.get('date') or
             f.get('matchDate') or f.get('startTime') or '')
    home  = (f.get('homeTeamName') or f.get('hjemmelag') or
             (f.get('homeTeam') or {}).get('name') or
             (f.get('homeTeam') or {}).get('fullName') or '')
    away  = (f.get('awayTeamName') or f.get('bortelag') or
             (f.get('awayTeam') or {}).get('name') or
             (f.get('awayTeam') or {}).get('fullName') or '')
    time  = (f.get('matchTime') or f.get('tid') or '')
    venue = (f.get('stadiumName') or f.get('bane') or f.get('venue') or
             f.get('stadium') or '')
    if date and (home or away):
        return {
            'date':  str(date)[:10],
            'time':  str(time)[:5],
            'home':  home,
            'away':  away,
            'venue': venue,
        }
    return None

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str  = datetime.utcnow().strftime('%Y-%m-%d')
    out_path   = os.path.join(DATA_DIR, 'football.json')

    # Load existing matches as fallback
    existing_matches = []
    if os.path.exists(out_path):
        try:
            with open(out_path, 'r', encoding='utf-8') as f:
                existing_matches = json.load(f).get('matches', [])
        except Exception:
            pass

    html = None

    # 1. Try Playwright
    try:
        print('Fetching with Playwright...')
        html = fetch_with_playwright()
        print('  Playwright OK')
    except Exception as e:
        print(f'  Playwright not available: {e}')

    # 2. Fall back to requests
    if not html:
        try:
            print('Falling back to requests...')
            html = fetch_with_requests()
            print('  requests OK')
        except Exception as e:
            print(f'  requests also failed: {e}')

    matches = []
    if html:
        matches = parse_next_data(html)
        print(f'  __NEXT_DATA__: {len(matches)} matches')
        if not matches:
            matches = parse_beautifulsoup(html)
            print(f'  BeautifulSoup: {len(matches)} matches')

    if not matches:
        print('  No matches found — keeping existing data')
        matches = existing_matches

    # Keep only upcoming, sorted
    upcoming = []
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    for m in matches:
        try:
            d = datetime.strptime(m['date'][:10], '%Y-%m-%d')
            if d >= now:
                upcoming.append(m)
        except Exception:
            upcoming.append(m)
    upcoming.sort(key=lambda x: x.get('date', ''))

    out = {
        'updated': today_str,
        'team':    'Larvik Turn',
        'source':  URL,
        'note':    'Oppdateres daglig. Klikk lenken for fullstendig oversikt.',
        'matches': upcoming[:8],
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {out_path} ({len(upcoming)} upcoming matches)')

if __name__ == '__main__':
    main()
