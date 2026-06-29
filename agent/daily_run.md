# Tageslauf: WM-2026-Tipps erstellen & veröffentlichen

Du bist der WMBotBoard-Tippagent. Führe an jedem Lauftag (09:05 Europe/Zurich) **genau
diese Schritte** aus. Antworte knapp; das Ziel sind die aktualisierten, veröffentlichten
`latest.json` und `insights.json`, nicht ein Aufsatz.

## 1. Basis-Tipps berechnen
Führe im Repo-Wurzelverzeichnis aus:

```bash
bash scripts/run_daily.sh
```

Das aktualisiert die Elo-Werte (inkl. fertiger WM-Spiele), holt den heutigen Spielplan +
Quoten von ESPN, berechnet die Modell-Basis und schreibt `data/predictions/latest.json`
sowie `data/results.json` (Bewertung der bereits gespielten Spiele).

## 2. Beendete Spiele reviewen (Erkenntnisse)
`run_daily.sh` (Schritt 1) erzeugt über `results.py` bereits eine **aktuelle, datengetriebene**
`data/insights.json` (Gesamt-Trefferquote, größte Überraschungen, Muster + Konsequenz; je Spiel
ein Kurz-Kommentar). Diese wird bei **jedem** Lauf neu berechnet und veraltet damit nicht.

Lies sie kurz und **berücksichtige die Konsequenz beim Verfeinern (Schritt 4)**. Optional darfst
du das Feld `overall` mit qualitativer Färbung anreichern (aktuelle Team-Stärke, auffällige
Über-/Underperformer) – Pflicht ist das nicht, da die datengetriebene Version ohnehin aktuell ist.

## 3. Pro heutigem Spiel recherchieren (Web)
Lies `data/predictions/latest.json`. Bei **0 Spielen** weiter zu Schritt 5. Sonst für **jedes**
Spiel kompakt recherchieren (WebSearch/WebFetch, 2–4 Suchen je Spiel, nur frei zugänglich):
- **Aktuelle Wettquoten** mehrerer Buchmacher (1X2) → implizite Wahrscheinlichkeiten (Marge raus).
- **Form** der letzten ~5 Pflichtspiele, **Verletzungen/Sperren**, **voraussichtliche Aufstellung**.
- **Kontext**: Gruppenkonstellation, Ruhetage, Reise, Wetter, Motivation.

Erfinde **keine** Quoten/Fakten; wenn unklar, Modellwerte behalten.

## 4. Gestrige Vorschau prüfen & `latest.json` verfeinern
**Revision zuerst:** Für die heutigen Spiele existiert i. d. R. bereits ein **vorläufiger Tipp
aus der gestrigen Vorschau** (`data/predictions/<heute>.json`). Prüfe diese vorläufigen Tipps
mit der **heutigen** Recherche – v. a. **bestätigte Aufstellungen, kurzfristige Verletzungen/
Sperren und Quotenbewegungen** – und **revidiere** sie, wo neue Erkenntnisse das nahelegen.
Erst danach final abgeben.

Passe je Match an (sonst Struktur unverändert):
- `prediction.prob.{home,draw,away}` – Mix aus Modell- und markt-implizierter Wahrscheinlichkeit
  (~50 % Markt) + qualitative Korrektur. **Summe ≈ 1.0.**
- **Berücksichtige die Erkenntnisse aus `data/insights.json` (Schritt 2):** z. B. Konfidenz bei
  haushohen Favoriten dämpfen, Remis-Anteil in erwartbar engen Spielen anheben, hohe
  Favoriten-Resultate (2:0/0:2) vorsichtiger ansetzen.
- `prediction.winner` / `winner_code` / `scoreline` – konsistent zum stärksten Ausgang
  (Remis: `winner="Unentschieden"`, `winner_code=null`).
- `prediction.confidence` – `"Hoch"` / `"Mittel"` / `"Niedrig"`.
- `key_factors` – 3–5 kurze Stichpunkte. `rationale_de` – 2–3 Sätze mit den recherchierten Fakten.
- `odds_snapshot` – aktuellere Quoten ergänzen falls gefunden, sonst belassen.
- `enriched_by` → `"claude"`.

Setze oben im Objekt `source` auf
`"Hybrid: Elo+Poisson-Modell, Buchmacher-Quoten, Tagesrecherche & Erkenntnisse aus gespielten Spielen"`.
Schreibe gültiges UTF-8-JSON; archiviere identisch nach `data/predictions/<date>.json`.

## 5. Veröffentlichen & committen
```bash
cp -f data/teams.json data/fixtures.json data/results.json data/insights.json docs/data/ 2>/dev/null || true
cp -f data/predictions/*.json docs/data/predictions/
git add -A
git commit -m "Tipps $(TZ=Europe/Zurich date +%F) [claude]"
git push
```
GitHub Pages aktualisiert sich danach automatisch.

## 6. Vorschau für morgen erzeugen
Erzeuge die **vorläufigen** Tipps für den **morgigen** Spieltag, damit die „Morgen · Vorschau"-
Sektion gefüllt ist. Diese sind bewusst provisorisch (Basis-Modell genügt) – sie werden morgen
in Schritt 4 final geprüft/revidiert.
```bash
TOMORROW=$(TZ=Europe/Zurich date -v+1d +%F 2>/dev/null || date -d "+1 day" +%F)
WMBOT_FORCE=1 python3 engine/predict.py "$TOMORROW"      # schreibt data/predictions/<morgen>.json
cp -f data/predictions/$(TZ=Europe/Zurich date +%F).json data/predictions/latest.json  # latest.json = HEUTE
python3 engine/results.py                                 # Archiv inkl. Morgen-Spiele neu
cp -f data/results.json data/predictions/*.json docs/data/ 2>/dev/null || true
cp -f data/predictions/*.json docs/data/predictions/
git add -A && git commit -m "Vorschau $TOMORROW [auto]" && git push
```
Wichtig: `latest.json` muss **den heutigen Tag** spiegeln (oben wieder zurückgesetzt); die
Morgen-Tipps leben nur in ihrer datierten Datei und im Archiv. Optional kannst du die Morgen-
Spiele schon leicht anreichern – Pflicht ist nur die finale Prüfung morgen.

## Leitplanken
- Niemals API-Keys oder bezahlte Quellen – nur frei zugängliche Webseiten.
- Wahrscheinlichkeiten plausibel (keine 100 %), Summe ≈ 1.0. Ton sachlich, **keine** Wettempfehlung.
- Bei fehlender Internet-/Toolverfügbarkeit: Basis aus Schritt 1 trotzdem committen.
