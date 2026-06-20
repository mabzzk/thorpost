#!/usr/bin/env python3
"""
Fetch commodity prices relevant to the steel/metals industry.
Strategy:
  1. yfinance library  (handles Yahoo Finance auth properly)
  2. stooq.com CSV     (reliable fallback, no key needed)
  3. World Bank API    (final fallback, monthly averages)
Writes to data/steel.json
"""

import json
import os
import csv
import io
import urllib.request
from datetime import datetime

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

COMMODITIES = [
    {'name': 'Jernmalm (SGX)',   'yf': 'TIO=F', 'stooq': 'tio.f',  'unit': 'USD/t', 'wb': None},
    {'name': 'Stål HRC (USA)',   'yf': 'HRC=F', 'stooq': 'hrc.f',  'unit': 'USD/t', 'wb': None},
    {'name': 'Kull (Newcastle)', 'yf': 'MTF=F', 'stooq': 'mtf.f',  'unit': 'USD/t', 'wb': 'PCOALAUUSD'},
]


# ── Method 1: yfinance ────────────────────────────────────────────────────────
def fetch_yfinance(symbol):
    if not HAS_YFINANCE:
        return None
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='5d')
        if hist.empty:
            return None
        latest = hist.iloc[-1]
        prev   = hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
        price      = float(latest['Close'])
        prev_close = float(prev['Close'])
        change     = round(price - prev_close, 2)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0
        info = ticker.info or {}
        currency = info.get('currency', 'USD')
        return {'price': round(price, 2), 'currency': currency,
                'change': change, 'change_pct': change_pct}
    except Exception as e:
        print(f'  yfinance failed for {symbol}: {e}')
        return None


# ── Method 2: stooq.com CSV ───────────────────────────────────────────────────
def fetch_stooq(symbol):
    url = f'https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv'
    try:
        if HAS_REQUESTS:
            r = requests.get(url, headers=HEADERS, timeout=12)
            text = r.text
        else:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                text = resp.read().decode('utf-8', errors='ignore')

        reader = csv.DictReader(io.StringIO(text))
        rows = [row for row in reader if row.get('Close', 'N/D') not in ('N/D', '', None)]
        if not rows:
            return None
        rows.sort(key=lambda r: r.get('Date', ''), reverse=True)
        latest = rows[0]
        prev   = rows[1] if len(rows) > 1 else rows[0]
        price      = float(latest['Close'])
        prev_close = float(prev['Close'])
        change     = round(price - prev_close, 2)
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0
        return {'price': round(price, 2), 'currency': 'USD',
                'change': change, 'change_pct': change_pct}
    except Exception as e:
        print(f'  stooq failed for {symbol}: {e}')
        return None


# ── Method 3: World Bank (monthly average, fallback) ─────────────────────────
def fetch_worldbank(indicator):
    if not indicator:
        return None
    url = f'https://api.worldbank.org/v2/en/indicator/{indicator}?format=json&mrv=2&frequency=M'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ThorPost/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data or len(data) < 2 or not data[1]:
            return None
        entries = [e for e in data[1] if e.get('value') is not None]
        if not entries:
            return None
        entries.sort(key=lambda e: e.get('date', ''), reverse=True)
        latest = entries[0]
        prev   = entries[1] if len(entries) > 1 else entries[0]
        price      = float(latest['value'])
        prev_val   = float(prev['value'])
        change     = round(price - prev_val, 2)
        change_pct = round(change / prev_val * 100, 2) if prev_val else 0
        period = latest.get('date', '')
        return {'price': round(price, 2), 'currency': 'USD',
                'change': change, 'change_pct': change_pct,
                'note': f'Månedlig gjennomsnitt ({period})'}
    except Exception as e:
        print(f'  World Bank failed for {indicator}: {e}')
        return None


def fetch_price(c):
    """Try yfinance → stooq → World Bank in order."""
    print(f"  Fetching {c['yf']} ({c['name']})...")

    result = fetch_yfinance(c['yf'])
    if result:
        print(f"    ✓ yfinance: {result['price']} {result['currency']}")
        return result

    result = fetch_stooq(c['stooq'])
    if result:
        print(f"    ✓ stooq: {result['price']} USD")
        return result

    result = fetch_worldbank(c.get('wb'))
    if result:
        print(f"    ✓ World Bank: {result['price']} USD (monthly)")
        return result

    print(f"    ✗ All sources failed for {c['yf']}")
    return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    path = os.path.join(DATA_DIR, 'steel.json')

    # Load last known prices as fallback
    last_known = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                old = json.load(f)
            for p in old.get('prices', []):
                last_known[p['symbol']] = p
        except Exception:
            pass

    prices = []
    for c in COMMODITIES:
        result = fetch_price(c)
        if result:
            prices.append({
                'name':   c['name'],
                'symbol': c['yf'],
                'unit':   c['unit'],
                **result,
            })
        elif c['yf'] in last_known:
            print(f"    → Using last known price for {c['name']}")
            prices.append(last_known[c['yf']])
        else:
            print(f"    → No data available for {c['name']}")

    out = {'updated': today, 'prices': prices}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path} ({len(prices)}/{len(COMMODITIES)} prices)')


if __name__ == '__main__':
    main()
