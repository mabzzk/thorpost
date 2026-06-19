# Thorpost

En personlig nettavis til Thor — oppdateres automatisk hver morgen.

## Innhold

| Seksjon | Kilde | Oppdatering |
|---|---|---|
| Vær i Larvik | api.met.no (yr.no) | Daglig kl. 07:00 |
| Havtemperatur | seatemperature.info | Daglig kl. 07:00 |
| Larvik Turn kamper | fotball.no | Daglig kl. 07:00 |
| Nyheter (5 stk) | NRK, OP.no, Friidrett.no, Reuters | Daglig kl. 07:00 |
| Nedtellinger | Hardkodet + kampdata | Live i nettleser |
| Bildegalleri | img/-mappen | Manuelt |
| Donald Duck | GoComics (lenke) | Daglig (live link) |

---

## Oppsett på GitHub Pages

1. Opprett et nytt GitHub-repository kalt `thorpost` på https://github.com/mabzzk
2. Last opp alle filer (eller push med `git`)
3. Gå til **Settings → Pages → Source**: velg **Deploy from a branch** → Branch: `main` → Folder: `/ (root)`
4. Klikk **Save** — siden er live på **https://mabzzk.github.io/thorpost/**

### Aktiver automatisk oppdatering

1. Gå til **Settings → Actions → General**
2. Under **Workflow permissions**, velg **Read and write permissions**
3. Klikk **Save**

Etter dette kjøres data-oppdateringen automatisk kl. 07:00–08:00 norsk tid hver dag.
Du kan også kjøre den manuelt: **Actions → Oppdater Thorpost daglig → Run workflow**

---

## Tilpasning

### Bislett Games-dato
Oppdater dette i `index.html` (rundt linje 350) én gang i året:
```javascript
const bislettDate = new Date(2027, 5, 3); // Juni 3, 2027
// Merk: måneder er 0-indeksert (0=januar, 5=juni)
```

### Innsjøtemperaturer (Farris og Ulfsbakktjern)
Det finnes ingen automatisert kilde for disse. Oppdater manuelt i `data/weather.json`:
```json
"water": {
  "ocean": 15.7,
  "farris": 20.5,
  "ulfsbakktjern": 18.3
}
```

### Bilder
Legg til eller erstatt bilder i `img/`-mappen.
**NB:** HEIC-filer (iPhone-format) støttes ikke i nettlesere.
Konverter til JPEG på Mac: Åpne i Fotos → Eksporter → JPEG

Legg til nye filnavn i `index.html` under `const IMAGES = [...]`.

### Nyhetskilder
Rediger `scripts/fetch_news.py` for å justere RSS-feeds eller søkeord.

### Kampdata
`fotball.no` bruker JavaScript-rendering, noe som gjør automatisk henting utfordrende.
Hvis kampdata ikke dukker opp automatisk, kan du legge til kamper manuelt i `data/football.json`:
```json
{
  "matches": [
    {
      "date": "2026-07-12",
      "time": "18:00",
      "home": "Larvik Turn",
      "away": "Motstanderlaget",
      "venue": "Louisenlund"
    }
  ]
}
```

---

## Filstruktur

```
thorpost/
├── index.html                  ← Nettsiden
├── img/                        ← Bilder til karusellen
├── data/
│   ├── weather.json            ← Oppdateres daglig av GitHub Actions
│   ├── news.json               ← Oppdateres daglig (inkl. arkiv)
│   └── football.json           ← Oppdateres daglig
├── scripts/
│   ├── fetch_weather.py        ← Henter vær fra met.no + havtemperatur
│   ├── fetch_news.py           ← Henter nyheter fra RSS-feeds
│   └── fetch_football.py       ← Henter kampprogram fra fotball.no
└── .github/
    └── workflows/
        └── update.yml          ← Kjøres kl. 07:00 norsk tid
```
