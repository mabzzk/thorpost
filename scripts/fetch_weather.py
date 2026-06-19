#!/usr/bin/env python3
"""
Fetch weather data for Larvik from met.no API + ocean temperature from seatemperature.info
Writes to data/weather.json
"""

import json
import re
import os
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    import urllib.request as _req
    import urllib.error
    requests = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')

LAT, LON = 59.0543, 10.0280
HEADERS = {'User-Agent': 'ThorPost/1.0 (personal newspaper; github.com/thorpost)'}

REMARKS = {
    'boiling':      "Skikkelig varmt i dag, Thor! Husk solkrem, sitteputen og masse vann.",
    'warm_sunny':   "Fin sommerdag i Larvik! Shorts er obligatorisk, og en tur langs fjorden er å anbefale.",
    'perfect':      "Perfekt dag ute, Thor – ikke mange som disse i Norge. Nyt hvert minutt!",
    'warm_cloudy':  "Behagelig og lunt, selv om sola gjemmer seg litt. Grillkveld kanskje?",
    'partly':       "Litt av hvert fra himmelen i dag, men ingenting å klage over!",
    'overcast':     "Overskyet, men rolig. Ta på en jakke og gå ut uansett, Thor.",
    'light_rain':   "Lett regn i dag. Paraply er lurt, men ikke la det ødelegge dagen.",
    'heavy_rain':   "Styrtregn! Perfekt dag for en god kopp kaffe og en god bok hjemme.",
    'cold_sunny':   "Klarvær men frisk luft – husk et ekstra lag, Thor.",
    'cold':         "Kaldt i dag. Varmmat, tykke sokker og en god film er dagens oppskrift.",
    'snow_heavy':   "MYE SNØ! Nå er det tid for å ta frem snøfreseren, Thor. Naboenes uuttalte helt!",
    'snow_light':   "Lett snøfall over Larvik. Kle deg som en skikkelig nordmann – lag på lag!",
    'sleet':        "Sludd og grøt ute. Ikke det fineste Larvik har å by på i dag.",
    'fog':          "Tåke over Larvik. Kjør forsiktig og ta det rolig.",
    'windy':        "Kraftig vind i dag, Thor – hold godt i hatten og la paraplyene ligge.",
    'default':      "En grei dag i Larvik. God morgen, Thor!"
}

def get(url, timeout=10):
    if requests:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    else:
        req = _req.Request(url, headers=HEADERS)
        with _req.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')

def fetch_met():
    url = f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={LAT}&lon={LON}'
    return json.loads(get(url))

def day_summary(timeseries, date_str):
    """Max/min/wind/precip/symbol for a calendar day (UTC)."""
    pts = [t for t in timeseries if t['time'].startswith(date_str + 'T')]
    if not pts:
        return None
    temps = [t['data']['instant']['details']['air_temperature'] for t in pts]
    winds = [t['data']['instant']['details']['wind_speed'] for t in pts]
    precip = sum(
        t['data'].get('next_1_hours', {}).get('details', {}).get('precipitation_amount', 0)
        for t in pts
    )
    # Prefer midday symbol
    symbol = None
    for hour in ['T10:00', 'T11:00', 'T12:00', 'T09:00', 'T13:00']:
        for t in pts:
            if hour in t['time']:
                sym = (t['data'].get('next_1_hours') or {}).get('summary', {}).get('symbol_code')
                if sym:
                    symbol = sym
                    break
        if symbol:
            break
    if not symbol:
        for t in pts:
            sym = (t['data'].get('next_1_hours') or {}).get('summary', {}).get('symbol_code')
            if sym:
                symbol = sym
                break
    return {
        'date': date_str,
        'symbol': symbol or 'partlycloudy_day',
        'temp_max': round(max(temps), 1),
        'temp_min': round(min(temps), 1),
        'wind_speed': round(sum(winds) / len(winds), 1),
        'precipitation': round(precip, 1),
    }

def fetch_ocean_temp():
    url = 'https://seatemperature.info/larvik-water-temperature.html'
    try:
        html = get(url)
        m = re.search(r'Water temperature in Larvik today is (\d+\.?\d*)°C', html)
        if m:
            return float(m.group(1))
        # Fallback: look for first standalone temperature number near "today"
        m = re.search(r'today[^<]{0,80}?(\d+\.\d)°C', html, re.IGNORECASE | re.DOTALL)
        if m:
            return float(m.group(1))
    except Exception as e:
        print(f'  Warning: ocean temp fetch failed: {e}')
    return None

def pick_remark(symbol, temp_max, precip):
    s = symbol.replace('_day', '').replace('_night', '').lower()
    if temp_max >= 28:
        return REMARKS['boiling']
    if temp_max >= 23 and 'clearsky' in s:
        return REMARKS['warm_sunny']
    if temp_max >= 20 and ('clearsky' in s or 'fair' in s):
        return REMARKS['perfect']
    if temp_max >= 17 and 'partly' in s:
        return REMARKS['warm_cloudy']
    if 'partly' in s or 'fair' in s:
        return REMARKS['partly']
    if precip >= 8 or 'heavyrain' in s:
        return REMARKS['heavy_rain']
    if precip > 0 or 'rain' in s:
        return REMARKS['light_rain']
    if 'heavysnow' in s:
        return REMARKS['snow_heavy']
    if 'snow' in s or 'sleet' in s:
        return REMARKS['snow_light'] if 'snow' in s else REMARKS['sleet']
    if 'fog' in s:
        return REMARKS['fog']
    if 'cloudy' in s:
        return REMARKS['overcast']
    if temp_max <= 4:
        return REMARKS['cold']
    if temp_max <= 10:
        return REMARKS['cold_sunny']
    return REMARKS['default']

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.utcnow()
    tomorrow = today + timedelta(days=1)
    today_str = today.strftime('%Y-%m-%d')
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')

    print('Fetching forecast from met.no...')
    met = fetch_met()
    ts = met['properties']['timeseries']

    td = day_summary(ts, today_str)
    tm = day_summary(ts, tomorrow_str)

    # Fallback if today has no UTC daytime data (we might be late in the day)
    if not td:
        yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        td = {
            'date': today_str, 'symbol': 'partlycloudy_day',
            'temp_max': ts[0]['data']['instant']['details']['air_temperature'],
            'temp_min': ts[0]['data']['instant']['details']['air_temperature'],
            'wind_speed': ts[0]['data']['instant']['details']['wind_speed'],
            'precipitation': 0.0
        }

    print('Fetching ocean temperature...')
    ocean = fetch_ocean_temp()
    print(f'  Ocean: {ocean}°C')

    remark = pick_remark(td['symbol'], td['temp_max'], td['precipitation'])

    out = {
        'updated': today_str,
        'today': td,
        'tomorrow': tm,
        'water': {
            'ocean': ocean,
            'farris': None,          # No public automated source — update manually if needed
            'ulfsbakktjern': None,   # No public automated source — update manually if needed
        },
        'remark': remark,
    }

    path = os.path.join(DATA_DIR, 'weather.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'Written: {path}')
    print(f'  Today:    {td["symbol"]}  {td["temp_max"]}°C  rain={td["precipitation"]}mm')
    print(f'  Tomorrow: {tm["symbol"]}  {tm["temp_max"]}°C')
    print(f'  Remark:   {remark[:70]}…')

if __name__ == '__main__':
    main()
