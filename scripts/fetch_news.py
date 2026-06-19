#!/usr/bin/env python3
"""
Fetch daily news for Thorpost from RSS feeds.
Categories: Larvik, Friidrett, Sport (NOR/Tottenham/LT), Stål & Industri
Writes to data/news.json and maintains rolling 30-day archive.
"""

import json
import re
import os
from datetime import datetime

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import urllib.request

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
HEADERS  = {'User-Agent': 'ThorPost/1.0 (personal news reader)'}

# ── RSS feeds ───────────────────────────────────────────────────────────────
FEEDS = {
    'larvik': [
        'https://www.nrk.no/vestfoldogtelemark/toppsaker.rss',   # NRK Vestfold og Telemark
        'https://www.op.no/rss.xml',                              # Østlands-Posten
        'https://www.op.no/rss',
        'https://www.op.no/feed',
    ],
    'running': [
        'https://www.nrk.no/sport/toppsaker.rss',
        'https://www.dagbladet.no/sport/rss.xml',
        'https://www.friidrett.no/rss',
    ],
    'sport': [
        'https://www.nrk.no/sport/toppsaker.rss',
        'https://www.dagbladet.no/sport/rss.xml',
        'https://www.vg.no/rss/create.php?categories=sport',
    ],
    'steel': [
        'https://feeds.reuters.com/reuters/businessNews',
        'https://feeds.reuters.com/reuters/companyNews',
        'https://www.mining.com/feed/',
    ],
}

# ── Keywords ────────────────────────────────────────────────────────────────
RUNNING_KW  = ['friidrett','maraton','marathon','løping','sprint','verdensrekord',
                'world record','diamond league','world athletics','100m','200m',
                '400m','800m','1500m','5000m','10000m','halvmaraton','atletik']
SPORT_KW    = ['norge','norsk','landslag','tottenham','spurs','larvik turn',
               'fotball','results','kamper','scoring','mål','serierunde']
STEEL_KW    = ['stål','steel','metall','metal','jernverk','industri',
               'råvarer','commodities','ironore','iron ore','coking coal']

# ── Helpers ──────────────────────────────────────────────────────────────────
def strip_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def fetch_url(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f'  fetch failed {url}: {e}')
        return None

def parse_feed(url):
    xml = fetch_url(url)
    if not xml:
        return []
    if HAS_FEEDPARSER:
        feed = feedparser.parse(xml)
        items = []
        for e in feed.entries[:15]:
            title   = strip_html(getattr(e, 'title', ''))
            summary = strip_html(getattr(e, 'summary', '') or getattr(e, 'description', ''))[:220]
            link    = getattr(e, 'link', '') or getattr(e, 'id', '')
            if title:
                items.append({'title': title, 'summary': summary, 'url': link})
        return items
    else:
        # Minimal XML parse without feedparser
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml)
            ns   = {'atom': 'http://www.w3.org/2005/Atom'}
            items = []
            for item in (root.findall('.//item') or root.findall('.//atom:entry', ns))[:15]:
                title   = (item.findtext('title') or item.findtext('atom:title', namespaces=ns) or '').strip()
                link    = (item.findtext('link') or item.findtext('atom:link', namespaces=ns) or '')
                desc    = strip_html(item.findtext('description') or item.findtext('atom:summary', namespaces=ns) or '')[:220]
                if title:
                    items.append({'title': title, 'summary': desc, 'url': link})
            return items
        except Exception as e:
            print(f'  parse failed: {e}')
            return []

def kw_match(item, keywords):
    text = (item['title'] + ' ' + item.get('summary','')).lower()
    return any(kw in text for kw in keywords)

def pick_from_feeds(feed_urls, filter_fn=None):
    for url in feed_urls:
        items = parse_feed(url)
        if not items:
            continue
        candidates = [i for i in items if filter_fn(i)] if filter_fn else items
        if candidates:
            return candidates[0]
        # If no keyword match, return first item as fallback only for category feeds
        if not filter_fn and items:
            return items[0]
    return None

# ── Main story builder ───────────────────────────────────────────────────────
def build_stories():
    stories = []
    used_urls = set()

    def add(story, category):
        if story and story.get('url') not in used_urls:
            story['category'] = category
            stories.append(story)
            used_urls.add(story.get('url'))

    # 1. Larvik local
    print('  Fetching Larvik news...')
    larvik = pick_from_feeds(FEEDS['larvik'])
    add(larvik, 'Larvik')

    # 2. Running / athletics
    print('  Fetching running news...')
    running = pick_from_feeds(FEEDS['running'], lambda i: kw_match(i, RUNNING_KW))
    if not running:
        running = pick_from_feeds(FEEDS['running'])
    add(running, 'Friidrett')

    # 3. Sports results (NOR, Tottenham, Larvik Turn)
    print('  Fetching sport results...')
    sport = pick_from_feeds(FEEDS['sport'], lambda i: kw_match(i, SPORT_KW))
    if not sport:
        sport = pick_from_feeds(FEEDS['sport'])
    add(sport, 'Sport')

    # 4. Steel / metals industry
    print('  Fetching steel/industry news...')
    steel = pick_from_feeds(FEEDS['steel'], lambda i: kw_match(i, STEEL_KW))
    add(steel, 'Stål & Industri')

    # 5. Fill remaining slot with any NRK sport story
    if len(stories) < 5:
        extras = parse_feed('https://www.nrk.no/sport/toppsaker.rss')
        for e in extras:
            if e.get('url') not in used_urls:
                e['category'] = 'Sport'
                stories.append(e)
                used_urls.add(e.get('url'))
                if len(stories) >= 5:
                    break

    return stories[:5]

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    news_path = os.path.join(DATA_DIR, 'news.json')

    # Load existing for archive
    existing = {'stories': [], 'archive': []}
    if os.path.exists(news_path):
        try:
            with open(news_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            pass

    archive    = existing.get('archive', [])
    old_stories = existing.get('stories', [])
    old_date   = existing.get('updated', '')

    # Archive yesterday's stories
    if old_stories and old_date and old_date != today_str:
        archive.insert(0, {'date': old_date, 'stories': old_stories})
        archive = archive[:30]

    print('Fetching news stories...')
    stories = build_stories()
    print(f'  Got {len(stories)} stories')
    for s in stories:
        print(f"    [{s.get('category','?')}] {s['title'][:65]}")

    out = {
        'updated': today_str,
        'stories': stories,
        'archive': archive,
    }
    with open(news_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {news_path}')

if __name__ == '__main__':
    main()
