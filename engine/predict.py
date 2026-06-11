"""Erzeugt die Basis-Tipps für die Spiele eines Tages (Elo+Poisson-Modell + ESPN-Quoten).

Schreibt data/predictions/<datum>.json und data/predictions/latest.json.

Dies ist die *Basis*. Die Cloud-Routine (agent/daily_run.md) verfeinert anschließend
`rationale_de`, `key_factors` und `odds_snapshot` mit aktueller Web-Recherche und kann
die Wahrscheinlichkeiten leicht anpassen ("enriched_by": "claude").
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import fetch_fixtures as ff
from elo import expected_goals, match_probabilities, DEFAULT_RATING
from names import canon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELO = os.path.join(ROOT, "data", "elo.json")
TEAMS = os.path.join(ROOT, "data", "teams.json")
PRED_DIR = os.path.join(ROOT, "data", "predictions")

HOSTS = {"USA", "MEX", "CAN"}       # Gastgeber 2026 -> leichter Heimvorteil
MARKET_WEIGHT = 0.5                  # Gewicht der Buchmacher-Quoten ggü. dem Modell


def _elo_entry(elo: dict, name: str) -> dict:
    e = elo.get(canon(name))
    if e:
        return e
    return {"rating": DEFAULT_RATING, "gf": None, "ga": None, "ppg": None, "form_ppg10": None}


def _confidence(p_top: float, agree: bool) -> str:
    if p_top >= 0.60 and agree:
        return "Hoch"
    if p_top >= 0.45:
        return "Mittel"
    return "Niedrig"


def _rationale(home, away, fav_name, probs, score, market) -> str:
    p = round(max(probs["p_home"], probs["p_draw"], probs["p_away"]) * 100)
    base = f"Das Modell sieht {fav_name} vorne ({p}%). Wahrscheinlichstes Resultat {score}."
    if market:
        base += " Quoten und Modell stimmen weitgehend überein." if market.get("agree") \
            else " Die Buchmacher sehen es etwas anders als das Modell."
    return base


def predict_match(m: dict, elo: dict, teams: dict) -> dict | None:
    hc, ac = m["home"].get("code"), m["away"].get("code")
    if hc not in teams or ac not in teams:
        return None  # K.o.-Platzhalter / noch nicht feststehend

    he, ae = _elo_entry(elo, m["home"]["name"]), _elo_entry(elo, m["away"]["name"])
    neutral = hc not in HOSTS
    lam_h, lam_a = expected_goals(
        he["rating"], ae["rating"], neutral=neutral,
        gf_a=he["gf"], ga_b=ae["ga"], gf_b=ae["gf"], ga_a=he["ga"],
    )
    model = match_probabilities(lam_h, lam_a)

    # Mit Markt-impliziten Wahrscheinlichkeiten mischen (falls vorhanden)
    probs = {"p_home": model["p_home"], "p_draw": model["p_draw"], "p_away": model["p_away"]}
    market_info = None
    odds = m.get("odds")
    if odds and odds.get("implied"):
        im = odds["implied"]
        w = MARKET_WEIGHT
        probs = {
            "p_home": round((1 - w) * model["p_home"] + w * im["home"], 4),
            "p_draw": round((1 - w) * model["p_draw"] + w * im["draw"], 4),
            "p_away": round((1 - w) * model["p_away"] + w * im["away"], 4),
        }
        model_fav = max(("p_home", "p_draw", "p_away"), key=lambda k: model[k])
        market_fav = max(im, key=im.get)
        market_info = {"agree": model_fav.replace("p_", "") == market_fav, "implied": im}

    # Sieger bestimmen
    key = max(probs, key=probs.get)
    outcome = key.replace("p_", "")  # home | draw | away
    if key == "p_home":
        winner, winner_code = m["home"]["name"], hc
    elif key == "p_away":
        winner, winner_code = m["away"]["name"], ac
    else:
        winner, winner_code = "Unentschieden", None
    # Resultat konsistent zum vorhergesagten Ausgang wählen
    scoreline = model["score_by_outcome"][outcome]

    fav_name = winner if winner_code else (m["home"]["name"] if probs["p_home"] >= probs["p_away"] else m["away"]["name"])
    p_top = max(probs.values())
    conf = _confidence(p_top, market_info["agree"] if market_info else False)

    return {
        "id": m["id"],
        "kickoff_utc": m["date_utc"],
        "venue": m["venue"],
        "city": m["city"],
        "group": m.get("group"),
        "home": {"code": hc, "name": m["home"]["name"], "logo": teams[hc]["logo"], "elo": he["rating"], "form_ppg10": he["form_ppg10"]},
        "away": {"code": ac, "name": m["away"]["name"], "logo": teams[ac]["logo"], "elo": ae["rating"], "form_ppg10": ae["form_ppg10"]},
        "prediction": {
            "winner": winner,
            "winner_code": winner_code,
            "scoreline": scoreline,
            "prob": {"home": probs["p_home"], "draw": probs["p_draw"], "away": probs["p_away"]},
            "confidence": conf,
            "expected_goals": {"home": model["lambda_home"], "away": model["lambda_away"]},
            "over_2_5": model["over_2_5"],
            "btts": model["btts"],
            "top_scorelines": model["top_scorelines"],
        },
        "odds_snapshot": odds,
        "key_factors": [],
        "rationale_de": _rationale(m["home"], m["away"], fav_name, probs, scoreline, market_info),
        "enriched_by": "model",
    }


def run(date_str: str) -> dict:
    elo = json.load(open(ELO, encoding="utf-8"))
    teams = json.load(open(TEAMS, encoding="utf-8"))
    matches = ff.fetch(date_str.replace("-", ""))
    preds = [p for p in (predict_match(m, elo, teams) for m in matches) if p]
    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(preds),
        "source": "elo+poisson model + ESPN odds",
        "matches": preds,
    }


def _already_enriched(date_str: str) -> bool:
    """True, wenn für den Tag bereits durch die Claude-Schicht angereicherte Tipps
    vorliegen. Verhindert, dass der GitHub-Actions-Fallback diese überschreibt."""
    path = os.path.join(PRED_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return False
    try:
        prev = json.load(open(path, encoding="utf-8"))
    except Exception:
        return False
    return prev.get("matches") and any(m.get("enriched_by") == "claude" for m in prev["matches"])


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Schutz: bereits angereicherte Tagestipps nicht durch die Modell-Basis überschreiben
    # (Override mit WMBOT_FORCE=1).
    if not os.environ.get("WMBOT_FORCE") and _already_enriched(date_str):
        print(f"Tipps für {date_str} sind bereits angereichert – Neuberechnung übersprungen.")
        return

    out = run(date_str)
    os.makedirs(PRED_DIR, exist_ok=True)
    for path in (os.path.join(PRED_DIR, f"{date_str}.json"), os.path.join(PRED_DIR, "latest.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{out['count']} Tipps für {date_str} -> data/predictions/{date_str}.json (+ latest.json)")
    for m in out["matches"]:
        pr = m["prediction"]
        print(f"  {m['home']['name']} vs {m['away']['name']}: {pr['winner']} {pr['scoreline']} "
              f"(H{int(pr['prob']['home']*100)}/D{int(pr['prob']['draw']*100)}/A{int(pr['prob']['away']*100)}, {pr['confidence']})")


if __name__ == "__main__":
    main()
