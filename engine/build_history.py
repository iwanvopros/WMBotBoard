"""Berechnet aktuelle Elo-Ratings + Form-/Trefferdaten aus der Länderspiel-Historie.

Quelle: data/sources/results.csv (martj42/international_results, kein API-Key).

- Elo wird über die gesamte Historie chronologisch konvergiert (korrekte aktuelle Stärke;
  jüngste Spiele dominieren das Rating ohnehin).
- Trefferraten (Tore für/gegen) und Form (Punkte/Spiel) stammen aus dem 3-Jahres-Fenster,
  passend zur Vorgabe "Historie der letzten 3 Jahre".

Ergebnis: data/elo.json  ->  { "<kanon. Name>": {rating, gf, ga, ppg, matches_3y, ...} }
"""

from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict
from datetime import date

from elo import update_ratings, DEFAULT_RATING
from names import canon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "data", "sources", "results.csv")
OUT = os.path.join(ROOT, "data", "elo.json")
RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def refresh_results():
    """Lädt die aktuelle Länderspiel-Historie (damit neue Ergebnisse die Elo speisen).
    Bei Fehler wird die vorhandene lokale Datei weiterverwendet."""
    try:
        req = urllib.request.Request(RESULTS_URL, headers={"User-Agent": "WMBotBoard"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) > 100_000:  # Plausibilitätscheck
            os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
            with open(RESULTS, "wb") as f:
                f.write(data)
            print(f"Historie aktualisiert ({len(data)//1024} KB)")
    except Exception as e:
        print(f"Hinweis: Historie nicht aktualisiert ({e}); nutze lokale Datei.")

# Turnier-Gewicht K je Wettbewerb (wichtigere Spiele -> stärkere Anpassung)
def k_for(tournament: str) -> float:
    t = (tournament or "").lower()
    if "world cup" in t and "qual" not in t:
        return 60.0
    if "euro" in t or "copa" in t or "nations" in t or "africa cup" in t or "asian cup" in t:
        return 50.0
    if "qualif" in t:
        return 40.0
    if "friendly" in t:
        return 20.0
    return 30.0


def build(as_of: date | None = None, years: int = 3) -> dict:
    as_of = as_of or date.today()
    cutoff = as_of.replace(year=as_of.year - years)

    ratings = defaultdict(lambda: DEFAULT_RATING)
    # 3-Jahres-Form: Listen je Team
    gf = defaultdict(list)   # erzielte Tore
    ga = defaultdict(list)   # kassierte Tore
    pts = defaultdict(list)  # Punkte je Spiel (3/1/0)
    last_played = {}

    rows = []
    with open(RESULTS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["home_score"] or not r["away_score"]:
                continue
            rows.append(r)
    rows.sort(key=lambda r: r["date"])

    for r in rows:
        d = r["date"]
        if d > as_of.isoformat():
            break
        h, a = canon(r["home_team"]), canon(r["away_team"])
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except ValueError:
            continue
        neutral = str(r.get("neutral", "")).strip().upper() in ("TRUE", "1", "YES")
        rh, ra = ratings[h], ratings[a]
        ratings[h], ratings[a] = update_ratings(rh, ra, hs, as_, k=k_for(r["tournament"]), neutral=neutral)
        last_played[h] = d
        last_played[a] = d

        if d >= cutoff.isoformat():
            gf[h].append(hs); ga[h].append(as_)
            gf[a].append(as_); ga[a].append(hs)
            pts[h].append(3 if hs > as_ else 1 if hs == as_ else 0)
            pts[a].append(3 if as_ > hs else 1 if as_ == hs else 0)

    out = {}
    teams = set(ratings) | set(gf)
    for t in teams:
        n = len(gf[t])
        recent_pts = pts[t][-10:]
        out[t] = {
            "rating": round(ratings[t], 1),
            "matches_3y": n,
            "gf": round(sum(gf[t]) / n, 3) if n else None,
            "ga": round(sum(ga[t]) / n, 3) if n else None,
            "ppg": round(sum(pts[t]) / n, 3) if n else None,
            "form_ppg10": round(sum(recent_pts) / len(recent_pts), 3) if recent_pts else None,
            "last_played": last_played.get(t),
        }
    return out


def main():
    refresh_results()
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    top = sorted(data.items(), key=lambda kv: kv[1]["rating"], reverse=True)[:15]
    print(f"Elo berechnet für {len(data)} Nationen -> {OUT}")
    print("Top 15:")
    for name, d in top:
        print(f"  {d['rating']:7.1f}  {name:24} (Form PPG10: {d['form_ppg10']})")


if __name__ == "__main__":
    main()
