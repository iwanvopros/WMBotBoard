# ⚽ WM 2026 · BotBoard

Täglicher Tipp-Agent für die Fussball-Weltmeisterschaft 2026 mit Live-Webinterface –
**komplett ohne API-Keys**. Jeden Morgen um **07:00 (Europe/Zurich)** berechnet ein
Hybrid-Modell die Tipps für die anstehenden Spiele und veröffentlicht sie auf einer
statischen Website mit zwei Bereichen: **„Vor dem Spiel"** (Tipps) und **„Live Games"**
(Live-Verfolgung).

## Wie es funktioniert

```
07:00 Europe/Zurich  ──>  GitHub Actions (.github/workflows/daily.yml)   [gratis, kein API-Key]
  └─ scripts/run_daily.sh
        ├─ build_history.py  Elo aus 3 Jahren Historie + fertige WM-Spiele live aus ESPN
        ├─ build_data.py     Spielplan, Teams, Gruppen, Quoten von ESPN
        └─ predict.py        Tipps (Elo + Poisson + Quoten)  → latest.json
  └─ git commit/push         GitHub Pages aktualisiert die Website automatisch

(optional) Claude-Verfeinerung via agent/daily_run.md:
  Form, Verletzungen, News, Quoten → reichert rationale_de & key_factors an.
```

Das **Frontend** (`docs/`) liest die Tipps aus `docs/data/predictions/latest.json` und
pollt für den Live-Bereich die ESPN-API direkt im Browser (alle 30 s).

### Neubewertung während des Turniers
- **Team-Stärke:** `build_history.py` lädt die Länderspiel-Historie täglich neu **und** speist
  fertige WM-Spiele sofort aus ESPN ins Elo ein → Auf-/Abwertungen wirken nach jedem Spiel.
- **Verletzungen/Form/News:** über die **täglich frisch geladenen Wettquoten** eingepreist
  (Markt reagiert auf Ausfälle); optional zusätzlich durch die Claude-Recherche-Schicht.

## Datenquellen (alle frei, ohne Key)

| Zweck | Quelle |
|------|--------|
| Spielplan, Live-Scores, Wettquoten | ESPN (inoffizielle JSON-API, `fifa.world`) |
| Historie / Elo-Kalibrierung | [martj42/international_results](https://github.com/martj42/international_results) |
| Gruppen / Stammdaten | [rezarahiminia/worldcup2026](https://github.com/rezarahiminia/worldcup2026) |
| Form, Verletzungen, aktuelle Quoten | Web-Recherche im Tageslauf |

## Tipp-Modell (Hybrid)

1. **Elo** (World-Football-Stil, Tor-Differenz-gewichtet) je Nation aus der Historie.
2. **Poisson**: aus der Elo-Differenz erwartete Tore → Wahrscheinlichkeit für jedes Resultat,
   Sieg/Remis/Niederlage, Over/Under 2.5, „beide treffen".
3. **Markt**: Buchmacher-Quoten → implizite Wahrscheinlichkeiten (Marge entfernt), gemischt.
4. **Recherche** (Claude im Tageslauf): Form, Verletzungen, News → qualitative Korrektur +
   Begründung auf Deutsch.

## Lokal ausführen

```bash
# Tipps für heute (oder ein Datum) berechnen und nach docs/ veröffentlichen
bash scripts/run_daily.sh 2026-06-11

# Website lokal ansehen
python3 -m http.server 8000 --directory docs
# -> http://localhost:8000
```

Voraussetzung: Python ≥ 3.10 (keine externen Pakete). Internet für ESPN/Historie.

## Projektstruktur

```
engine/        Python-Modell (stdlib): elo, build_history, fetch_fixtures, build_data, predict
data/          elo.json, teams.json, fixtures.json, predictions/  (Quell-Outputs)
docs/          statische Website (GitHub Pages) + docs/data (veröffentlichte Kopie)
agent/         daily_run.md – Anweisung der Cloud-Routine um 07:00
scripts/       run_daily.sh – Modell-Pipeline + Publish
```

## Deployment

1. Repo (öffentlich) auf GitHub pushen.
2. **Settings → Pages**: Source = `main` Branch, Ordner `/docs` → öffentliche URL.
3. **GitHub Actions** ist über `.github/workflows/daily.yml` bereits eingerichtet: läuft
   täglich 05:00 UTC (07:00 Europe/Zurich), kostenlos, committet die neuen Tipps. Manuell
   testen: Tab **Actions → Tägliche WM-Tipps → Run workflow**.
4. *(Optional)* Reichhaltigere Begründungen via Claude: `agent/daily_run.md` über eine
   Claude-Code-Routine ausführen lassen (nutzt dein Abo, keine bezahlte API).

> Tipps sind Modell-/Rechercheschätzungen und **keine** Wettempfehlung.
