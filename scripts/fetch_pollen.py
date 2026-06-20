#!/usr/bin/env python3
"""
Fetch pollen forecast for Ulfsbakk/Larvik from yr.no.
URL: https://www.yr.no/nb/andre-varsler/1-32872/Norge/Vestfold/Larvik/Ulfsbakk
Looks for the "Luften rundt Ulfsbakk" pollen section.
Uses Playwright since yr.no is JS-rendered.
Appends pollen data to data/weather.json.
"""

import json
import os
import re
from datetime import datetime

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
YR_URL   = 'https://www.yr.no/nb/andre-varsler/1-32872/Norge/Vestfold/Larvik/Ulfsbakk'

# Pollen level mapping — yr.no uses Norwegian level labels
LEVEL_MAP = {
    'ingen':     {'label': 'Ingen',     'num': 0, 'color': '#aaa'},
    'lav':       {'label': 'Lav',       'num': 1, 'color': '#6aaa48'},
    'moderat':   {'label': 'Moderat',   'num': 2, 'color': '#f5c518'},
    'høy':       {'label': 'Høy',       'num': 3, 'color': '#e07b39'},
    'svært høy': {'label': 'Svært høy', 'num': 4, 'color': '#c0392b'},
}


def parse_level(text):
    """Parse a pollen level string to structured data."""
    t = (text or '').strip().lower()
    for key, val in LEVEL_MAP.items():
        if key in t:
            return val
    return {'label': text.strip().title(), 'num': 0, 'color': '#aaa'}


def fetch_with_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('  Playwright not available')
        return []

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        try:
            print(f'  Navigating to {YR_URL}')
            page.goto(YR_URL, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            # Try to find pollen section — yr.no renders pollen in a table/list
            # Look for elements containing pollen type names
            pollen_types_no = ['gress', 'bjørk', 'or ', 'hassel', 'burot', 'salix', 'älg', 'alm', 'einer']

            # Strategy: get all text content and parse pollen rows
            # yr.no pollen section has rows with plant name + level
            html = page.content()
            print(f'  Got {len(html)} bytes of HTML')

            # Look for pollen section by searching for known plant names
            # yr.no uses aria-labels or data attributes for pollen info
            # Try evaluating JS to extract pollen table data
            pollen_data = page.evaluate("""
                () => {
                    const results = [];
                    // Look for pollen-related elements
                    const allText = document.querySelectorAll('[class*="pollen"], [class*="Pollen"], [data-testid*="pollen"]');
                    allText.forEach(el => {
                        results.push({ tag: el.tagName, class: el.className, text: el.innerText.trim().substring(0, 200) });
                    });
                    // Also look for the section header
                    const headers = document.querySelectorAll('h2, h3, h4');
                    headers.forEach(h => {
                        if (h.innerText && h.innerText.toLowerCase().includes('luften')) {
                            const parent = h.closest('section') || h.parentElement;
                            if (parent) results.push({ tag: 'SECTION', class: 'air-section', text: parent.innerText.trim().substring(0, 500) });
                        }
                    });
                    return results;
                }
            """)
            print(f'  Found {len(pollen_data)} pollen elements via JS')

            # Parse the extracted text
            for item in pollen_data:
                text = item.get('text', '')
                if not text:
                    continue
                # Parse lines like "Gress\nLav" or "Bjørk\nModerat"
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    if any(pt in line.lower() for pt in pollen_types_no):
                        level_text = lines[i+1] if i+1 < len(lines) else 'ukjent'
                        level = parse_level(level_text)
                        results.append({
                            'type':  line.title(),
                            'level': level['label'],
                            'num':   level['num'],
                            'color': level['color'],
                        })

            # Fallback: regex scan of full page text
            if not results:
                print('  Trying regex fallback on page text...')
                page_text = page.evaluate("() => document.body.innerText")
                # Look for "Luften rundt" section
                m = re.search(r'Luften rundt[^\n]*\n(.*?)(?:\n\n|\Z)', page_text, re.DOTALL | re.IGNORECASE)
                if m:
                    section = m.group(1)
                    for pt in pollen_types_no:
                        pm = re.search(rf'({pt}[^\n]*)\n([^\n]+)', section, re.IGNORECASE)
                        if pm:
                            level = parse_level(pm.group(2))
                            results.append({
                                'type':  pm.group(1).strip().title(),
                                'level': level['label'],
                                'num':   level['num'],
                                'color': level['color'],
                            })

        except Exception as e:
            print(f'  Playwright error: {e}')
        finally:
            browser.close()

    return results


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    weather_path = os.path.join(DATA_DIR, 'weather.json')

    print('Fetching pollen forecast from yr.no...')
    pollen = fetch_with_playwright()
    print(f'  Got {len(pollen)} pollen entries')
    for p in pollen:
        print(f"    {p['type']}: {p['level']}")

    # Append to weather.json
    if os.path.exists(weather_path):
        with open(weather_path, 'r', encoding='utf-8') as f:
            weather = json.load(f)
    else:
        weather = {}

    weather['pollen'] = pollen if pollen else []
    weather['pollen_updated'] = today

    with open(weather_path, 'w', encoding='utf-8') as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    print(f'Updated: {weather_path}')


if __name__ == '__main__':
    main()
