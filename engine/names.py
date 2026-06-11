"""Einheitliche Team-Namens-Normalisierung.

Die Historie (martj42/international_results) und die Repo-CSV (worldcup2026) nutzen
englische Standardnamen. ESPN weicht bei einigen Teams ab. Diese Map bringt ESPN- und
sonstige Schreibweisen auf den kanonischen Namen, mit dem die Elo-Werte indexiert sind.
"""

# ESPN-/Alternativschreibweise  ->  kanonischer Name (= results.csv / repo name_en)
ALIASES = {
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "Czechia": "Czech Republic",
    "Congo DR": "DR Congo",
    "DR Congo": "DR Congo",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "USA": "United States",
    "United States": "United States",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Cabo Verde": "Cape Verde",
    "Côte d'Ivoire": "Ivory Coast",
    "Curacao": "Curaçao",
}


def canon(name: str) -> str:
    """Kanonischer Team-Name für Elo-/Historie-Lookups."""
    if not name:
        return ""
    n = name.strip()
    return ALIASES.get(n, n)
