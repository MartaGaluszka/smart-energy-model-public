#!/usr/bin/env bash
# Shadow: RF16 + pogoda ICON solo (OpenMeteo-forecast).
#
# Gdy ENSEMBLE_PRIMARY=1, primary jest ensemble — ICON zostaje w shadow
# do closeoutów (porównanie vs ENS / CS4). Wołane z mlops/_ensemble_primary.sh.
#
# Archiwum: daily_icon / midday_icon / peak_icon → forecast_history.
# Wyłączenie: FORECAST_ICON_SHADOW=0

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BASE_LABEL="${1:-manual}"
ENABLED="${FORECAST_ICON_SHADOW:-1}"

if [[ "${ENABLED}" != "1" && "${ENABLED}" != "true" && "${ENABLED}" != "yes" ]]; then
  echo "ICON shadow wyłączony (FORECAST_ICON_SHADOW=${ENABLED})"
  exit 0
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

RUN_LABEL="${BASE_LABEL}_icon"
OUT_CSV="data/processed/pv_forecast_icon.csv"

echo ""
echo "=== ICON SHADOW (RF16 + OpenMeteo-forecast) | ${RUN_LABEL} ==="

# Jawne OpenMeteo-forecast — bez tego ENSEMBLE_PRIMARY=1 zaciągnąłby ensemble.
WEATHER_FORECAST_SOURCE_LIKE='OpenMeteo-forecast' \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" \
    --days 3 --top 5 \
    --run-label "${RUN_LABEL}" \
    --out "${OUT_CSV}"

echo "✓ ICON shadow OK → ${OUT_CSV} + archiwum ${RUN_LABEL}"
