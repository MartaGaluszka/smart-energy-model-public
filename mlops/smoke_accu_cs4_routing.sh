#!/usr/bin/env bash
# Szybki test przed startem XI: Accu → CS4 w routing operacyjnym.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PROJECT_ROOT="${ROOT}"
# shellcheck source=/dev/null
source "${ROOT}/mlops/_venv.sh"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
set -a
# shellcheck source=/dev/null
[[ -f "${ROOT}/.env" ]] && source "${ROOT}/.env"
set +a
echo "ACCU_CS4_UI=${ACCU_CS4_UI:-0}"
"${PYTHON}" - <<'PY'
import os
from src.weather.forecast_routing import accu_cs4_routing_enabled, resolve_forecast_display

if not accu_cs4_routing_enabled():
    raise SystemExit("❌ ACCU_CS4_UI nie włączone — ustaw ACCU_CS4_UI=1 w .env")

db = os.getenv("DATABASE_PATH", "data/energy_model.db")
day = "2026-11-01"
r = resolve_forecast_display(day, db_path=db)
print(f"✓ {day} regime={r.regime} display={r.display_model}")
if r.display_model != "cs4":
    raise SystemExit(f"❌ Oczekiwano CS4 dla {day} (Accu w DB) — sprawdź weather_notes")
print("✓ Go-live CS4 routing OK")
PY
