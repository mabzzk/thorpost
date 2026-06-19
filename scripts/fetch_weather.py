#!/usr/bin/env python3
"""
Fetch weather data for Larvik from met.no API + ocean temperature from seatemperature.info
+ sunrise/sunset from met.no sunrise API + daily thought
Writes to data/weather.json
"""

import json
import re
import os
import hashlib
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

THOUGHTS = [
    "Livet er kort, men bredt nok til å romme mye glede.",
    "Det er ikke vinden som bestemmer retningen, men seilet.",
    "En god latter er solskinn i et hus. – William Makepeace Thackeray",
    "Den som ikke risikerer noe, risikerer alt.",
    "Morgenstund har gull i munn — spesielt i Larvik.",
    "Alle gode ting er tre. Du har allerede to.",
    "Fremtiden tilhører dem som tror på drømmenes skjønnhet. – Eleanor Roosevelt",
    "Det er ikke hva vi har, men hvem vi er, som gjør oss rike.",
    "En klok mann snakker fordi han har noe å si; en tosk fordi han må si noe. – Platon",
    "Livet er 10% hva som skjer med oss og 90% hvordan vi reagerer på det.",
    "Den som søker, finner — om han er tålmodig nok.",
    "Glede deles ikke, den mangedobles.",
    "Det er aldri for sent å bli den du kunne ha vært. – George Eliot",
    "Norsk natur er som en god venn — alltid der, uansett vær.",
    "Ingenting er umulig for den som ikke selv skal gjøre det.",
    "Et smil koster ingenting, men er verdt mye.",
    "Den som planter trær, vet at han ikke selv vil sitte i skyggen.",
    "Vis meg hvem du omgås, så skal jeg si deg hvem du er.",
    "Kjærligheten er den eneste skatten som øker når den deles ut.",
    "En dag uten latter er en dag bortkastet. – Charlie Chaplin",
    "Det finnes ikke dårlig vær — bare dårlige klær.",
    "Lykke er ikke å få det du vil, men å ville det du har.",
    "Den største reisen begynner med et enkelt skritt. – Lao Tzu",
    "Vennskap er ett hjerte i to kropper. – Aristoteles",
    "Gjør deg ikke større enn du er, men heller ikke mindre.",
    "Kunnskap er makt — og den kan ikke stjeles fra deg.",
    "Alt som er verdt å gjøre, er verdt å gjøre med hjertet.",
    "Livet gir deg det du trenger, ikke alltid det du vil ha.",
    "Den beste tid å plante et tre var for tjue år siden. Den nest beste er i dag.",
    "Vær den forandringen du vil se i verden. – Mahatma Gandhi",
    "En god bok er som en god venn — alltid klar for deg.",
    "Havet er alltid like vakkert, uansett om solen skinner eller regnet faller.",
    "Den som tier, samtykker ikke — den tenker bare grundigere.",
    "Lykken er ikke et mål, men en reisefølge.",
    "Store drømmer starter med små skritt.",
    "Norske fjorder har lært oss at dybde er vakker.",
    "Det er i motgang vi finner ut hvem vi virkelig er.",
    "Latter er den korteste avstand mellom to mennesker. – Victor Borge",
    "Tid er den dyreste valutaen — bruk den med omhu.",
    "Den som har helse, har alt. Den som ikke har helse, har ett ønske.",
    "Kreativitet er intelligens som har det gøy. – Albert Einstein",
    "Gode minner er den beste arven vi kan gi videre.",
    "En optimist ser muligheten i hver vanskelighet.",
    "Det er ikke lengden på livet, men dybden i det som teller. – Ralph Waldo Emerson",
    "Ydmykhet er ikke å tenke mindre om seg selv — det er å tenke mindre på seg selv.",
    "Skjønnhet finnes overalt — du trenger bare å stoppe opp og se.",
    "Den som gir av seg selv, blir aldri fattig.",
    "Sjøen kaller på dem som lytter — og Larvik hører alltid.",
    "Mot er ikke fravær av frykt, men å gå videre til tross for den.",
    "Hvert eneste menneske har en gave — noen finner den tidlig, andre sent.",
]

def get_thought(date_str):
    """Select a deterministic daily thought/quote based on date."""
    idx = int(hashlib.md5(date_str.encode()).hexdigest(), 16) % len(THOUGHTS)
    return THOUGHTS[idx]

def get_sunrise_sunset(date_str):
    """Fetch sunrise and sunset times for Larvik from met.no sunrise API."""
    month = int(date_str[5:7])
    # Norway: CEST (UTC+2) March-October, CET (UTC+1) November-February
    offset = '+02:00' if 3 <= month <= 10 else '+01:00'
    url = f'https://api.met.no/weatherapi/sunrise/3.0/sun?lat={LAT}&lon={LON}&date={date_str}&offset={offset}'
    try:
        txt = get(url)
        data = json.loads(txt)
        props = data.get('properties', {})
        sunrise_raw = props.get('sunrise', {}).get('time', '')
        sunset_raw  = props.get('sunset',  {}).get('time', '')
        # Extract HH:MM — the time string is e.g. "2026-06-20T04:06:48+02:00"
        sunrise = sunrise_raw[11:16] if len(sunrise_raw) > 15 else ''
        sunset  = sunset_raw[11:16]  if len(sunset_raw)  > 15 else ''
        return sunrise, sunset
    except Exception as e:
        print(f'  Sunrise/sunset error: {e}')
        return '', ''

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

    print('Fetching sunrise/sunset...')
    sunrise, sunset = get_sunrise_sunset(today_str)
    print(f'  Sunrise: {sunrise}  Sunset: {sunset}')

    remark = pick_remark(td['symbol'], td['temp_max'], td['precipitation'])
    thought = get_thought(today_str)
    print(f'  Thought: {thought[:60]}…')

    out = {
        'updated': today_str,
        'today': td,
        'tomorrow': tm,
        'water': {
            'ocean': ocean,
            'farris': None,          # No public automated source — update manually if needed
            'ulfsbakktjern': None,   # No public automated source — update manually if needed
        },
        'sun': {'sunrise': sunrise, 'sunset': sunset},
        'remark': remark,
        'thought': thought,
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
