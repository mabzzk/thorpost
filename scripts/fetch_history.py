#!/usr/bin/env python3
"""
Fetch "this day in history" from Norwegian Wikipedia REST API.
Falls back to English Wikipedia if Norwegian endpoint returns no events.
Writes to data/history.json
"""

import json
import os
import urllib.request
from datetime import datetime

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
HEADERS  = {'User-Agent': 'ThorPost/1.0 (personal newspaper; github.com/mabzzk/thorpost)'}


def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        print(f'  fetch failed ({url}): {e}')
        return None


def get_events(month, day, lang='no'):
    url = f'https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}'
    data = fetch_url(url)
    if data and data.get('events'):
        return data['events']
    return []


def pick_events(events, n=3):
    """Pick n events spread across history (old, middle, recent)."""
    if not events:
        return []
    events_sorted = sorted(events, key=lambda e: e.get('year', 0))
    total = len(events_sorted)
    if total <= n:
        return events_sorted
    # Spread picks: 25%, 50%, 75% of sorted list
    indices = [max(0, total * p // 100) for p in [25, 50, 75]][:n]
    return [events_sorted[i] for i in indices]


def format_event(e, lang):
    text = e.get('text', '') or ''
    year = e.get('year', '')
    pages = e.get('pages', [])
    url = ''
    thumbnail = ''
    if pages:
        p = pages[0]
        url = (p.get('content_urls') or {}).get('desktop', {}).get('page', '')
        thumb = p.get('thumbnail') or {}
        src = thumb.get('source', '')
        # Upscale small thumbnails to at least 200px width
        if src:
            thumbnail = src.replace('/80px-', '/200px-').replace('/100px-', '/200px-')
    return {'year': year, 'text': text, 'url': url, 'thumbnail': thumbnail, 'lang': lang}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow()
    month = today.month
    day   = today.day
    today_str = today.strftime('%Y-%m-%d')

    # Try Norwegian Wikipedia first, fall back to English
    print(f'Fetching history for {month}/{day}...')
    events = get_events(month, day, lang='no')
    lang = 'no'
    if not events:
        print('  Norwegian Wikipedia returned no events — trying English...')
        events = get_events(month, day, lang='en')
        lang = 'en'

    picks = pick_events(events, n=3)
    out_events = [format_event(e, lang) for e in picks]
    print(f'  Got {len(out_events)} history events (lang={lang})')
    for e in out_events:
        print(f"    {e['year']}: {str(e['text'])[:65]}")

    out = {
        'updated': today_str,
        'month':   month,
        'day':     day,
        'events':  out_events,
    }
    path = os.path.join(DATA_DIR, 'history.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path}')


if __name__ == '__main__':
    main()
