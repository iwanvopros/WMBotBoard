"""Elo-Ratingsystem (World-Football-Stil) + Poisson-Resultatmodell.

Reine Standardbibliothek, keine Abhängigkeiten.

- Elo mit Tor-Differenz-Gewichtung -> aktuelle Stärke jeder Nation.
- Aus der Elo-Differenz wird eine Tor-"Supremacy" abgeleitet, daraus zwei Poisson-Raten
  (lambda_home/away). Das Poisson-Modell liefert dann Sieg/Remis/Niederlage-
  Wahrscheinlichkeiten, das wahrscheinlichste Resultat, Over/Under und BTTS.
"""

import math

# --- Tuning-Parameter ---------------------------------------------------------
HOME_ADV = 60.0            # Elo-Bonus für ein nicht-neutrales Heimteam (Gastgeber)
SUPREMACY_PER_ELO = 0.0035  # Tor-Supremacy je Elo-Punkt (400 Elo ~ 1.4 Tore Unterschied)
BASE_TOTAL_GOALS = 2.70    # durchschnittliche Gesamttore pro Länderspiel
RAW_BLEND = 0.25           # Gewicht der historischen Trefferraten ggü. reinem Elo-Modell
MAX_GOALS = 8              # Obergrenze der Poisson-Tabelle je Team
DEFAULT_RATING = 1500.0


def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def _goal_diff_multiplier(gd: int) -> float:
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8.0


def update_ratings(ra, rb, ga, gb, k=40.0, neutral=True):
    """Gibt (neues_ra, neues_rb) nach einem Spiel zurück. ga/gb = Tore Heim/Gast."""
    ha = 0.0 if neutral else HOME_ADV
    ea = expected_score(ra + ha, rb)
    if ga > gb:
        sa = 1.0
    elif ga < gb:
        sa = 0.0
    else:
        sa = 0.5
    delta = k * _goal_diff_multiplier(ga - gb) * (sa - ea)
    return ra + delta, rb - delta


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def expected_goals(ra, rb, neutral=True, gf_a=None, ga_b=None, gf_b=None, ga_a=None):
    """Erwartete Tore (lambda) für Heim/Gast aus Elo-Supremacy, optional mit
    historischen Trefferraten gemischt."""
    ha = 0.0 if neutral else HOME_ADV
    supremacy = ((ra + ha) - rb) * SUPREMACY_PER_ELO
    lam_a = (BASE_TOTAL_GOALS + supremacy) / 2.0
    lam_b = (BASE_TOTAL_GOALS - supremacy) / 2.0

    # Historische Raten einmischen (falls vorhanden): erwartete Tore A = avg(A erzielt, B kassiert)
    if None not in (gf_a, ga_b):
        lam_a = (1 - RAW_BLEND) * lam_a + RAW_BLEND * ((gf_a + ga_b) / 2.0)
    if None not in (gf_b, ga_a):
        lam_b = (1 - RAW_BLEND) * lam_b + RAW_BLEND * ((gf_b + ga_a) / 2.0)

    return max(0.15, lam_a), max(0.15, lam_b)


def match_probabilities(lam_a: float, lam_b: float) -> dict:
    """Faltet zwei unabhängige Poisson-Verteilungen zur gemeinsamen Resultat-Matrix
    und leitet alle Kennzahlen ab."""
    pa = [_poisson_pmf(lam_a, i) for i in range(MAX_GOALS + 1)]
    pb = [_poisson_pmf(lam_b, j) for j in range(MAX_GOALS + 1)]

    p_home = p_draw = p_away = 0.0
    p_over25 = p_btts = 0.0
    best = (0, 0, 0.0)
    best_by = {"home": (0, 0, 0.0), "draw": (0, 0, 0.0), "away": (0, 0, 0.0)}
    scorelines = []
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = pa[i] * pb[j]
            scorelines.append((i, j, p))
            if i > j:
                p_home += p
                outcome = "home"
            elif i < j:
                p_away += p
                outcome = "away"
            else:
                p_draw += p
                outcome = "draw"
            if p > best_by[outcome][2]:
                best_by[outcome] = (i, j, p)
            if i + j > 2.5:
                p_over25 += p
            if i >= 1 and j >= 1:
                p_btts += p
            if p > best[2]:
                best = (i, j, p)

    scorelines.sort(key=lambda x: x[2], reverse=True)
    top = [{"score": f"{i}:{j}", "p": round(p, 4)} for i, j, p in scorelines[:5]]

    return {
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
        "lambda_home": round(lam_a, 3),
        "lambda_away": round(lam_b, 3),
        "most_likely_score": f"{best[0]}:{best[1]}",
        "score_by_outcome": {k: f"{v[0]}:{v[1]}" for k, v in best_by.items()},
        "top_scorelines": top,
        "over_2_5": round(p_over25, 4),
        "btts": round(p_btts, 4),
    }
