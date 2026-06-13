"""Bewertet bereits gespielte WM-Spiele: verknüpft archivierte Tipps mit den
tatsächlichen ESPN-Resultaten und berechnet je Spiel eine Trefferquote.

Trefferquote (0–100 %), selbst definiertes Schema:
  + 50  Tendenz richtig (Heimsieg / Remis / Auswärtssieg)
  + 20  Tordifferenz richtig
  + 20  exaktes Resultat richtig
  + 0–10  Modell-Überzeugung = 10 × Wahrscheinlichkeit, die das Modell dem
          tatsächlich eingetretenen Ausgang zugewiesen hatte (Kalibrierung)

Ergebnis: data/results.json  – nach Gruppe sortiert, inkl. Gesamtquote.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone

import fetch_fixtures as ff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_DIR = os.path.join(ROOT, "data", "predictions")
TEAMS = os.path.join(ROOT, "data", "teams.json")
OUT = os.path.join(ROOT, "data", "results.json")
ARCHIVE = os.path.join(ROOT, "data", "predictions", "archive.json")
TOURNAMENT = "20260611-20260719"


def _team_groups() -> dict:
    try:
        return {c: v.get("group") for c, v in json.load(open(TEAMS, encoding="utf-8")).items()}
    except Exception:
        return {}


def _load_tips() -> dict:
    """Alle archivierten Tipps nach ESPN-Match-ID. Angereicherte (claude) gewinnen."""
    tips = {}
    for path in sorted(glob.glob(os.path.join(PRED_DIR, "*.json"))):
        if os.path.basename(path) == "latest.json":
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        for m in data.get("matches", []):
            mid = m.get("id")
            if not mid:
                continue
            prev = tips.get(mid)
            if prev is None or (m.get("enriched_by") == "claude" and prev.get("enriched_by") != "claude"):
                tips[mid] = m
    return tips


def _outcome(hs: int, as_: int) -> str:
    return "home" if hs > as_ else "away" if hs < as_ else "draw"


def _grade(tip: dict, hs: int, as_: int) -> dict:
    pred = tip["prediction"]
    # vorhergesagte Tore aus scoreline "x:y" (Heim:Gast)
    try:
        ph, pa = (int(x) for x in pred["scoreline"].split(":"))
    except (ValueError, KeyError):
        ph = pa = None

    actual = _outcome(hs, as_)
    pred_out = ("home" if pred.get("winner_code") == tip["home"]["code"]
                else "away" if pred.get("winner_code") == tip["away"]["code"]
                else "draw")

    tendenz = pred_out == actual
    tordiff = ph is not None and (ph - pa) == (hs - as_)
    exakt = ph is not None and ph == hs and pa == as_
    prob_actual = float(pred.get("prob", {}).get(actual, 0.0))

    score = (50 if tendenz else 0) + (20 if tordiff else 0) + (20 if exakt else 0) + 10 * prob_actual
    score = round(min(100.0, score), 1)

    verdict = ("Volltreffer" if exakt else "Tendenz + Tordifferenz" if (tendenz and tordiff)
               else "Tendenz richtig" if tendenz else "Daneben")
    return {
        "score": score,
        "factors": {"tendenz": tendenz, "tordifferenz": tordiff, "exakt": exakt,
                     "prob_actual": round(prob_actual, 3)},
        "verdict": verdict,
    }


def build() -> dict:
    tips = _load_tips()
    tg = _team_groups()
    finished = [m for m in ff.fetch(TOURNAMENT)
                if m.get("state") == "post"
                and str(m["home"].get("score", "")).lstrip("-").isdigit()
                and str(m["away"].get("score", "")).lstrip("-").isdigit()]

    graded, scores = [], []
    for m in finished:
        tip = tips.get(m["id"])
        if not tip:
            continue  # kein archivierter Tipp -> nicht bewertbar
        hs, as_ = int(m["home"]["score"]), int(m["away"]["score"])
        g = _grade(tip, hs, as_)
        scores.append(g["score"])
        pred = tip["prediction"]
        # Gruppe: aus dem Tipp, sonst aus teams.json (gleiche Gruppe beider Teams = Gruppenspiel)
        grp = tip.get("group")
        if not grp:
            hg, ag = tg.get(m["home"]["code"]), tg.get(m["away"]["code"])
            grp = hg if hg and hg == ag else None
        graded.append({
            "id": m["id"],
            "date_utc": m["date_utc"],
            "group": grp,
            "home": {"name": m["home"]["name"], "code": m["home"]["code"], "logo": tip["home"].get("logo")},
            "away": {"name": m["away"]["name"], "code": m["away"]["code"], "logo": tip["away"].get("logo")},
            "actual": f"{hs}:{as_}",
            "tip": {"scoreline": pred["scoreline"], "winner": pred["winner"],
                    "confidence": pred["confidence"], "prob": pred["prob"]},
            "result_score": g["score"],
            "factors": g["factors"],
            "verdict": g["verdict"],
        })

    # nach Gruppe gruppieren (A..L, dann K.o.-Runde)
    order = "ABCDEFGHIJKL"
    buckets: dict[str, list] = {}
    for gm in graded:
        key = gm["group"] or "K.o.-Runde"
        buckets.setdefault(key, []).append(gm)
    for v in buckets.values():
        v.sort(key=lambda x: x["date_utc"])

    def gkey(k: str):
        return (order.index(k), k) if k in order else (99, k)

    groups = [{"group": k, "matches": buckets[k]} for k in sorted(buckets, key=gkey)]

    exact = sum(1 for s in graded if s["factors"]["exakt"])
    tend = sum(1 for s in graded if s["factors"]["tendenz"])
    n = len(graded)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": n,
        "overall_quote": round(sum(scores) / n, 1) if n else 0,
        "tendency_rate": round(100 * tend / n) if n else 0,
        "exact_rate": round(100 * exact / n) if n else 0,
        "groups": groups,
    }


def dump_archive():
    """Schlankes Tipp-Archiv (alle je getippten Spiele nach ESPN-ID), damit das Frontend
    beendete Spiele live gegen die Tipps bewerten kann – ohne auf den Tageslauf zu warten."""
    tg = _team_groups()
    arch = {}
    for mid, t in _load_tips().items():
        p = t["prediction"]
        grp = t.get("group")
        if not grp:
            hg, ag = tg.get(t["home"]["code"]), tg.get(t["away"]["code"])
            grp = hg if hg and hg == ag else None
        arch[mid] = {
            "group": grp,
            "home": {"name": t["home"]["name"], "code": t["home"]["code"], "logo": t["home"].get("logo")},
            "away": {"name": t["away"]["name"], "code": t["away"]["code"], "logo": t["away"].get("logo")},
            "prediction": {"winner": p["winner"], "winner_code": p.get("winner_code"),
                            "scoreline": p["scoreline"], "prob": p["prob"], "confidence": p["confidence"]},
        }
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(arch, f, ensure_ascii=False, indent=2)
    print(f"{len(arch)} Tipps ins Archiv geschrieben -> data/predictions/archive.json")


def main():
    out = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    dump_archive()
    print(f"{out['count']} gespielte Spiele bewertet -> data/results.json")
    print(f"  Gesamt-Trefferquote: {out['overall_quote']}% | Tendenz {out['tendency_rate']}% | Exakt {out['exact_rate']}%")
    for g in out["groups"]:
        for m in g["matches"]:
            print(f"  [{g['group']}] {m['home']['name']} {m['actual']} {m['away']['name']}"
                  f"  (Tipp {m['tip']['scoreline']}) -> {m['result_score']}% {m['verdict']}")


if __name__ == "__main__":
    main()
