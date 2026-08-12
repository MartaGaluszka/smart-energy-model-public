#!/usr/bin/env bash
# CS4 na PRODUKCJI (dual) — drugi model obok 16 cech, ten sam launchd.
#
# Wołane z daily_workflow / midday_forecast / peak_arrival po primary.
# Archiwum: daily_cs4 / midday_cs4 / peak_cs4 → forecast_history + closeout.
#
# Wyłączenie: FORECAST_CS4_ENABLED=0 (alias: FORECAST_CS4_SHADOW=0)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BASE_LABEL="${1:-manual}"
CS4_MODEL="${PV_HOURLY_MODEL_CS4_PATH:-models/pv_hourly_model_cs4.joblib}"

# Preferuj FORECAST_CS4_ENABLED; stary alias SHADOW też działa
ENABLED="${FORECAST_CS4_ENABLED:-${FORECAST_CS4_SHADOW:-1}}"

if [[ "${ENABLED}" != "1" && "${ENABLED}" != "true" && "${ENABLED}" != "yes" ]]; then
  echo "CS4 dual wyłączony (FORECAST_CS4_ENABLED=${ENABLED})"
  exit 0
fi

if [[ ! -f "${PROJECT_ROOT}/${CS4_MODEL}" && ! -f "${CS4_MODEL}" ]]; then
  echo "❌ Brak ${CS4_MODEL} — CS4 ma być na produkcji. Uruchom:"
  echo "   ./mlops/train_dual_weekly.sh"
  exit 1
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

RUN_LABEL="${BASE_LABEL}_cs4"
OUT_CSV="data/processed/pv_forecast_cs4.csv"

echo ""
echo "=== CS4 PRODUKCJA (dual) | ${RUN_LABEL} | ${CS4_MODEL} ==="

PV_HOURLY_MODEL_PATH="${CS4_MODEL}" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/forecast_pv.py" \
    --days 3 --top 5 \
    --run-label "${RUN_LABEL}" \
    --no-operational-adjust \
    --out "${OUT_CSV}"

echo "✓ CS4 dual OK → ${OUT_CSV} + archiwum ${RUN_LABEL}"
