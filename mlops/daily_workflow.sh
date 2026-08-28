#!/usr/bin/env bash
# =============================================================================
# Smart Home PV — codzienny workflow wdrożeniowy
#
# 1. Synchronizacja danych (FoxESS + Open-Meteo prognoza)
# 2. Prognoza PV: dziś + jutro + pojutrze + ranking godzin na urządzenia AGD
#
# Użycie ręczne:
#   ./mlops/daily_workflow.sh
#
# CRON — poranek (5:00, przed produkcją PV):
#   0 5 * * * /path/to/smart-energy-model/mlops/daily_workflow.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
#
# CRON — opcjonalnie południe (12:00, świeższe chmury na popołudnie):
#   0 12 * * * /path/to/smart-energy-model/mlops/midday_forecast.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1
#
# CRON — retrening (niedziela 5:00):
#   0 5 * * 0 cd /path/to/smart-energy-model && ./venv/bin/python scripts/train/train_hourly_model_tuning.py >> logs/train.log 2>&1
# =============================================================================

set -euo pipefail

# Katalog projektu (dwa poziomy w górę od mlops/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "======================================================================"
echo "Smart Home PV — daily workflow | ${TIMESTAMP}"
echo "Projekt: ${PROJECT_ROOT}"
echo "======================================================================"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
echo "✓ Python: ${PYTHON}"

run_step() {
  local label="$1"
  shift
  echo ""
  echo "--- ${label} ---"
  if "$@"; then
    echo "✓ ${label} — OK"
  else
    local code=$?
    echo "❌ ${label} — błąd (kod ${code})" >&2
    exit "${code}"
  fi
}

# Nie-fatalny: gdy FoxESS jest rate-limitowany (40402), pogoda i tak się zsynchronizuje —
# reszta workflow (prognoza, bateria) nie powinna zostać zablokowana chwilowym outage'em Fox.
echo ""
echo "--- Synchronizacja danych (FoxESS + Open-Meteo) ---"
if "$PYTHON" "${PROJECT_ROOT}/mlops/sync_data.py"; then
  echo "✓ Synchronizacja danych (FoxESS + Open-Meteo) — OK"
else
  sync_code=$?
  echo "⚠️  Synchronizacja FoxESS nie powiodła się (kod ${sync_code}) — kontynuuję z danymi pogodowymi / cache FoxESS" >&2
fi

run_step "Prognoza PV + harmonogram urządzeń (dziś + 2 dni)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" --days 3 --top 5 --run-label daily

# Shadow: CS4 + XGB+TS (produkcja nadal RF 16)
run_step "Prognoza CS4 (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_cs4_shadow.sh" daily

run_step "Prognoza XGB+TS (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_xgb_ts_shadow.sh" daily

run_step "Prognoza ensemble ICON+UKMO (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_ensemble_shadow.sh" daily

run_step "Routing pick (ensemble vs CS4)" \
  "$PYTHON" "${PROJECT_ROOT}/scripts/analysis/routing_decision.py" --date today --also-next 2

run_step "Bateria — poranek (tanio do 6:00 / prognoza PV)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/battery_advisor_report.py" --context morning

run_step "Sugestie baterii → notifications (T4.20)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/generate_battery_suggestions.py" --context morning

run_step "Bateria — plan sterowania (dry-run)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context morning

echo ""
echo "======================================================================"
echo "✅ Workflow zakończony pomyślnie | $(date '+%Y-%m-%d %H:%M:%S')"
echo "   Prognoza: ${PROJECT_ROOT}/data/processed/pv_forecast.csv"
echo "======================================================================"
