"""Holt WM-2026-Spiele von der inoffiziellen ESPN-JSON-API (kein API-Key).

Endpoint: site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard

Liefert normalisierte Matches inkl. Status (für Live), Venue, Team-Logos und – sofern
vorhanden – Wettquoten. Reine Standardbibliothek (urllib), damit es auch in der
Cloud-Routine ohne Zusatzpakete läuft.
"""

from __future__ import annotations

import json
import sys
import urllib.request

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 WMBotBoard"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def _competitor(c: dict) -> dict:
    t = c.get("team", {})
    return {
        "name": t.get("displayName"),
        "short": t.get("shortDisplayName"),
        "code": t.get("abbreviation"),
        "logo": t.get("logo") or (t.get("logos", [{}])[0].get("href") if t.get("logos") else None),
        "color": t.get("color"),
        "score": c.get("score"),
        "winner": c.get("winner"),
    }


def _american_to_prob(odds) -> float | None:
    """Amerikanische Quote -> implizite Wahrscheinlichkeit (inkl. Buchmacher-Marge)."""
    try:
        v = float(str(odds).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v < 0:
        return -v / (-v + 100.0)
    return 100.0 / (v + 100.0)


def _ml(side: dict) -> str | None:
    """Schlusskurs (close) der Moneyline einer Seite, sonst open."""
    if not isinstance(side, dict):
        return None
    for phase in ("close", "open"):
        p = side.get(phase)
        if isinstance(p, dict) and p.get("odds") is not None:
            return p["odds"]
    return None


def _odds(comp: dict) -> dict | None:
    odds = comp.get("odds")
    if not odds:
        return None
    o = odds[0]
    if not isinstance(o, dict):
        return None
    out = {
        "provider": o.get("provider", {}).get("name"),
        "details": o.get("details"),
        "over_under": o.get("overUnder"),
    }
    ml = o.get("moneyline", {})
    home_ml = _ml(ml.get("home", {}))
    away_ml = _ml(ml.get("away", {}))
    draw_ml = (o.get("drawOdds") or {}).get("moneyLine")
    out["moneyline"] = {"home": home_ml, "draw": draw_ml, "away": away_ml}

    # Implizite Wahrscheinlichkeiten (margin-normalisiert), falls alle drei vorhanden
    ph, pd, pa = (_american_to_prob(home_ml), _american_to_prob(draw_ml), _american_to_prob(away_ml))
    if None not in (ph, pd, pa):
        s = ph + pd + pa
        out["implied"] = {"home": round(ph / s, 4), "draw": round(pd / s, 4), "away": round(pa / s, 4)}
    return out


def normalize_event(e: dict) -> dict:
    comp = e.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[-1] if competitors else {})
    status = e.get("status", {}) or comp.get("status", {})
    stype = status.get("type", {})
    venue = comp.get("venue", {})
    addr = venue.get("address", {})
    return {
        "id": e.get("id"),
        "date_utc": e.get("date"),
        "name": e.get("name"),
        "state": stype.get("state"),          # pre | in | post
        "status": stype.get("description"),    # Scheduled, In Progress, Full Time, ...
        "completed": stype.get("completed"),
        "clock": status.get("displayClock"),
        "period": status.get("period"),
        "venue": venue.get("fullName"),
        "city": addr.get("city"),
        "country": addr.get("country"),
        "home": _competitor(home),
        "away": _competitor(away),
        "odds": _odds(comp),
    }


def fetch(dates: str | None = None, limit: int = 200) -> list[dict]:
    """dates: 'YYYYMMDD' oder 'YYYYMMDD-YYYYMMDD'. None = aktuelles Scoreboard."""
    url = f"{SCOREBOARD}?limit={limit}"
    if dates:
        url += f"&dates={dates}"
    data = _get(url)
    return [normalize_event(e) for e in data.get("events", [])]


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    # erlaubt '2026-06-11' -> '20260611'
    if arg and "-" in arg and len(arg) == 10:
        arg = arg.replace("-", "")
    matches = fetch(arg)
    print(json.dumps(matches, ensure_ascii=False, indent=2))
