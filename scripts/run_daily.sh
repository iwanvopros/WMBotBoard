#!/usr/bin/env bash
# Täglicher Modell-Lauf (Basis-Tipps). Erzeugt latest.json und kopiert die vom Frontend
# benötigten Dateien nach docs/data/. Idempotent und ohne externe Pakete lauffähig.
#
# Aufruf:  bash scripts/run_daily.sh [YYYY-MM-DD]
# Ohne Argument: heutiges Datum in Europe/Zurich.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Besten verfügbaren Python-Interpreter wählen (>=3.10, mit funktionierenden CA-Zerts).
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Kein python3 gefunden"; exit 1; }
echo "==> Interpreter: $($PY -V 2>&1)"

DATE="${1:-$(TZ=Europe/Zurich date +%F)}"
echo "==> WMBotBoard Tageslauf für $DATE"

echo "--> Elo aus Länderspiel-Historie aktualisieren"
"$PY" engine/build_history.py

echo "--> Spielplan/Teams von ESPN aktualisieren"
"$PY" engine/build_data.py

echo "--> Basis-Tipps berechnen"
"$PY" engine/predict.py "$DATE"

echo "--> Gespielte Spiele bewerten (Trefferquote)"
"$PY" engine/results.py

publish() {
  mkdir -p docs/data/predictions
  cp -f data/teams.json docs/data/teams.json
  cp -f data/fixtures.json docs/data/fixtures.json
  cp -f data/results.json docs/data/results.json 2>/dev/null || true
  cp -f data/predictions/*.json docs/data/predictions/ 2>/dev/null || true
  echo "--> Nach docs/data/ veröffentlicht"
}
publish

echo "==> Fertig. latest.json: $("$PY" -c 'import json;d=json.load(open("data/predictions/latest.json"));print(d["count"],"Tipps,",d["date"])')"
