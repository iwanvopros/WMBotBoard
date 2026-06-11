"""Erzeugt statische Stammdaten fürs Frontend:

- data/teams.json     -> { "<FIFA-Code>": {name, logo, color, group} }
- data/fixtures.json  -> kompletter Spielplan (alle WM-Spiele, normalisiert)

Quelle: ESPN (Teams/Logos/Spielplan) + Repo-CSV (Gruppen-Seed). Gruppen der
aufgelösten Playoff-Teams werden aus den Gruppenphasen-Paarungen abgeleitet.
"""

from __future__ import annotations

import csv
import json
import os

import fetch_fixtures as ff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_CSV = os.path.join(ROOT, "data", "sources", "teams.csv")
TEAMS_OUT = os.path.join(ROOT, "data", "teams.json")
FIXTURES_OUT = os.path.join(ROOT, "data", "fixtures.json")

GROUP_STAGE = "20260611-20260627"
FULL_TOURNAMENT = "20260611-20260719"


def _seed_groups() -> dict:
    """FIFA-Code -> Gruppe aus der Repo-CSV (nur die zur Auslosung bekannten Teams)."""
    seed = {}
    with open(TEAMS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code = (r.get("fifa_code") or "").strip()
            grp = (r.get("groups") or "").strip()
            if code and code != "TBD" and grp:
                seed[code] = grp
    return seed


def _derive_groups(group_events: list[dict], seed: dict) -> dict:
    """Vervollständigt die Gruppen-Map: in der Gruppenphase spielen nur Teams derselben
    Gruppe gegeneinander -> unbekannte Codes von bekannten Gegnern ableiten."""
    groups = dict(seed)
    edges = [(m["home"]["code"], m["away"]["code"]) for m in group_events
             if m["home"].get("code") and m["away"].get("code")]
    # Fixpunkt-Iteration: bekannte Gruppe auf Gegner übertragen
    for _ in range(5):
        changed = False
        for a, b in edges:
            if a in groups and b not in groups:
                groups[b] = groups[a]; changed = True
            elif b in groups and a not in groups:
                groups[a] = groups[b]; changed = True
        if not changed:
            break
    return groups


def main():
    group_events = ff.fetch(GROUP_STAGE)
    all_events = ff.fetch(FULL_TOURNAMENT)

    groups = _derive_groups(group_events, _seed_groups())

    # teams.json aus allen Wettbewerbsteilnehmern
    teams = {}
    for m in all_events:
        for side in ("home", "away"):
            t = m[side]
            code = t.get("code")
            # nur echte Nationen (in der Gruppen-Map); K.o.-Platzhalter (1A, RD16 W1, ...) auslassen
            if not code or code not in groups:
                continue
            teams.setdefault(code, {
                "name": t["name"],
                "logo": t["logo"],
                "color": t["color"],
                "group": groups.get(code),
            })

    with open(TEAMS_OUT, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)

    # Gruppe je Match anreichern (nur Gruppenphase eindeutig)
    for m in all_events:
        hc, ac = m["home"].get("code"), m["away"].get("code")
        m["group"] = groups.get(hc) if groups.get(hc) and groups.get(hc) == groups.get(ac) else None

    with open(FIXTURES_OUT, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    known = sum(1 for t in teams.values() if t["group"])
    print(f"teams.json: {len(teams)} Teams ({known} mit Gruppe) -> {TEAMS_OUT}")
    print(f"fixtures.json: {len(all_events)} Spiele -> {FIXTURES_OUT}")


if __name__ == "__main__":
    main()
