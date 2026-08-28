#!/usr/bin/env bash
# Popołudniowe odświeżenie (16:00): sync + prognoza + stan baterii przed szczytem 16–22.
#
# launchd: pl.smart-energy-model.peak

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== Peak arrival (16:00) | $(date '+%Y-%m-%d %H:%M:%S') ==="

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

run_step "Prognoza PV (peak)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" --days 3 --top 5 --run-label peak

run_step "Prognoza CS4 (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_cs4_shadow.sh" peak

run_step "Prognoza XGB+TS (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_xgb_ts_shadow.sh" peak

run_step "Prognoza ensemble ICON+UKMO (shadow)" \
  bash "${PROJECT_ROOT}/mlops/forecast_ensemble_shadow.sh" peak

run_step "Routing pick (ensemble vs CS4)" \
  "$PYTHON" "${PROJECT_ROOT}/scripts/analysis/routing_decision.py" --date today --also-next 2

run_step "Bateria — szczyt wieczorny 16–22" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/battery_advisor_report.py" --context peak

run_step "Sugestie baterii → notifications (T4.20)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/generate_battery_suggestions.py" --context peak

run_step "Bateria — plan sterowania (dry-run)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context peak

echo "=== Peak arrival OK ==="
