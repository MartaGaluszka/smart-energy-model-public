#!/usr/bin/env bash
# Shadow #2: XGB + TS (16 production + 8 NWP) — obok RF 16 (produkcja) i RF CS4.
#
# Wołane z daily_workflow / midday_forecast / peak_arrival po primary (+ CS4).
# Archiwum: daily_xgb_ts / midday_xgb_ts / peak_xgb_ts
#
# Wyłączenie: FORECAST_XGB_TS_SHADOW=0

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BASE_LABEL="${1:-manual}"
XGB_MODEL="${PV_HOURLY_MODEL_XGB_TS_PATH:-models/pv_hourly_model_xgb_ts.joblib}"
ENABLED="${FORECAST_XGB_TS_SHADOW:-1}"

if [[ "${ENABLED}" != "1" && "${ENABLED}" != "true" && "${ENABLED}" != "yes" ]]; then
  echo "XGB+TS shadow wyłączony (FORECAST_XGB_TS_SHADOW=${ENABLED})"
  exit 0
fi

if [[ ! -f "${PROJECT_ROOT}/${XGB_MODEL}" && ! -f "${XGB_MODEL}" ]]; then
  echo "⚠️  Brak ${XGB_MODEL} — pomijam shadow XGB+TS. Trening:"
  echo "   python scripts/train/train_xgb_ts_shadow.py"
  exit 0
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

RUN_LABEL="${BASE_LABEL}_xgb_ts"
OUT_CSV="data/processed/pv_forecast_xgb_ts.csv"

echo ""
echo "=== XGB+TS SHADOW | ${RUN_LABEL} | ${XGB_MODEL} ==="

# Zawsze ICON (OpenMeteo-forecast) — nawet gdy ENSEMBLE_PRIMARY=1.
PV_HOURLY_MODEL_PATH="${XGB_MODEL}" \
WEATHER_FORECAST_SOURCE_LIKE='OpenMeteo-forecast' \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" \
    --days 3 --top 5 \
    --run-label "${RUN_LABEL}" \
    --no-operational-adjust \
    --out "${OUT_CSV}"

echo "✓ XGB+TS shadow OK → ${OUT_CSV} + archiwum ${RUN_LABEL}"
