#!/usr/bin/env python3
"""
Fetch commodity prices relevant to the steel/metals industry:
  - Iron ore futures (TIO=F)
  - US HRC Steel futures (HRC=F)
  - Newcastle coal futures (MTF=F)
Uses Yahoo Finance's unofficial chart API — no key required.
Writes to data/steel.json
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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json',
}

COMMODITIES = [
    {'name': 'Jernmalm (SGX)',  'symbol': 'TIO=F',  'unit': 'USD/t'},
    {'name': 'Stål HRC (USA)',  'symbol': 'HRC=F',  'unit': 'USD/t'},
    {'name': 'Kull (Newcastle)','symbol': 'MTF=F',  'unit': 'USD/t'},
]


def fetch_price(symbol):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d'
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            data = r.json()
        else:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())

        result = (data.get('chart') or {}).get('result') or []
        if not result:
            return None
        meta = result[0].get('meta', {})
        price = meta.get('regularMarketPrice')
        prev  = meta.get('chartPreviousClose') or meta.get('previousClose')
        currency = meta.get('currency', 'USD')
        if price is None:
            return None
        change     = round(price - prev, 2) if prev else 0
        change_pct = round(change / prev * 100, 2) if prev else 0
        return {
            'price':      round(float(price), 2),
            'currency':   currency,
            'change':     change,
            'change_pct': change_pct,
        }
    except Exception as e:
        print(f'  Price fetch failed for {symbol}: {e}')
        return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    prices = []

    for c in COMMODITIES:
        print(f"  Fetching {c['symbol']} ({c['name']})...")
        result = fetch_price(c['symbol'])
        if result:
            prices.append({
                'name':       c['name'],
                'symbol':     c['symbol'],
                'unit':       c['unit'],
                **result,
            })
            arrow = '▲' if result['change'] > 0 else ('▼' if result['change'] < 0 else '—')
            print(f"    {result['price']} {result['currency']} {arrow} {result['change_pct']:+.1f}%")
        else:
            print(f"    No data for {c['symbol']}")

    out = {'updated': today, 'prices': prices}
    path = os.path.join(DATA_DIR, 'steel.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path} ({len(prices)}/{len(COMMODITIES)} prices)')


if __name__ == '__main__':
    main()
