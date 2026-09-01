#!/usr/bin/env bash
# Południowe odświeżenie: FoxESS (dziś) + pogoda + prognoza PV.
#
# CRON / launchd (12:00):
#   0 12 * * * /path/to/smart-energy-model/mlops/midday_forecast.sh >> /path/to/smart-energy-model/logs/cron.log 2>&1

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_ensemble_primary.sh"

echo ""
echo "=== Midday refresh | $(date '+%Y-%m-%d %H:%M:%S') ==="

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
# reszta workflow nie powinna zostać zablokowana chwilowym outage'em Fox.
echo ""
echo "--- Synchronizacja (FoxESS + Open-Meteo) ---"
if "$PYTHON" "${PROJECT_ROOT}/mlops/sync_data.py"; then
  echo "✓ Synchronizacja (FoxESS + Open-Meteo) — OK"
else
  sync_code=$?
  echo "⚠️  Synchronizacja FoxESS nie powiodła się (kod ${sync_code}) — kontynuuję z danymi pogodowymi / cache FoxESS" >&2
fi

run_pv_forecast_stack midday

run_step "Bateria — przed oknem tanio 13:00–15:00" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/battery_advisor_report.py" --context pre_cheap

run_step "Sugestie baterii → notifications (T4.20)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/generate_battery_suggestions.py" --context pre_cheap

run_step "Bateria — plan sterowania (dry-run)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context pre_cheap

echo "=== Midday refresh OK ==="
