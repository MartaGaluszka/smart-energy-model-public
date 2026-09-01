#!/usr/bin/env bash
# Ensemble ICON+UKMO → pv_forecast_ensemble.csv (shadow gdy ENSEMBLE_PRIMARY≠1).
#
# 1) Zapisuje prognozę ensemble do weather_data (osobny data_source)
# 2) Prognoza PV → data/processed/pv_forecast_ensemble.csv
#
# Gdy ENSEMBLE_PRIMARY=1, daily/midday/peak używają mlops/_ensemble_primary.sh
# (ensemble → pv_forecast.csv); ten skrypt zostaje dla trybu ICON-primary / ręcznego.
# Wyłączenie: FORECAST_ENSEMBLE_SHADOW=0

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BASE_LABEL="${1:-manual}"
ENABLED="${FORECAST_ENSEMBLE_SHADOW:-1}"

if [[ "${ENABLED}" != "1" && "${ENABLED}" != "true" && "${ENABLED}" != "yes" ]]; then
  echo "Ensemble ICON+UKMO shadow wyłączony (FORECAST_ENSEMBLE_SHADOW=${ENABLED})"
  exit 0
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

RUN_LABEL="${BASE_LABEL}_ensemble"
OUT_CSV="data/processed/pv_forecast_ensemble.csv"

echo ""
echo "=== ENSEMBLE ICON+UKMO SHADOW | ${RUN_LABEL} ==="

echo "--- Sync pogody ensemble (obok ICON, nie zamiast) ---"
"$PYTHON" "${PROJECT_ROOT}/mlops/sync_ensemble_weather.py"

echo "--- Prognoza PV na pogodzie ensemble ---"
WEATHER_FORECAST_SOURCE_LIKE='%ensemble%' \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" \
    --days 3 --top 5 \
    --run-label "${RUN_LABEL}" \
    --no-operational-adjust \
    --out "${OUT_CSV}"

echo "✓ Ensemble shadow OK → ${OUT_CSV} + archiwum ${RUN_LABEL}"
