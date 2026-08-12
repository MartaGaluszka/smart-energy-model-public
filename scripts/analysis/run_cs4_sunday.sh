#!/usr/bin/env bash
# CS4 jako KANDYDAT (nie nadpisuje produkcji / launchd).
#
# Produkcja = 16 cech → models/pv_hourly_model.joblib
# CS4 shadow = 19 cech → models/pv_hourly_model_cs4.joblib
#
# Użycie:
#   ./scripts/analysis/run_cs4_sunday.sh
#   ./scripts/analysis/run_cs4_sunday.sh --skip-train
#   ./scripts/analysis/run_cs4_sunday.sh --shadow-only

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT_ROOT="$ROOT"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLBACKEND=Agg
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

SKIP_TRAIN=0
SHADOW_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --skip-train) SKIP_TRAIN=1 ;;
    --shadow-only) SHADOW_ONLY=1; SKIP_TRAIN=1 ;;
  esac
done

echo "=== CS4 kandydat (produkcja zostaje 16 cech) ==="
echo "ROOT=$ROOT"

if [[ "$SHADOW_ONLY" -eq 0 && "$SKIP_TRAIN" -eq 0 ]]; then
  echo
  echo "[1/3] Trening CS4 → models/pv_hourly_model_cs4.joblib"
  "$PYTHON" scripts/train/train_hourly_model_tuning.py \
    --features cs4 \
    --model-path models/pv_hourly_model_cs4.joblib
fi

if [[ "$SHADOW_ONLY" -eq 0 ]]; then
  echo
  echo "[2/3] Gate compare_model_change (baseline=produkcja 16, candidate=CS4)"
  "$PYTHON" scripts/analysis/compare_model_change.py \
    --change "CS4 low+mid+clearness" \
    --baseline-model models/pv_hourly_model.joblib \
    --candidate-model models/pv_hourly_model_cs4.joblib \
    --train-start 2025-06-01 \
    --append-changelog || true
fi

echo
echo "[3/3] Shadow forecast CS4 (nie zmienia launchd)"
if [[ -f models/pv_hourly_model_cs4.joblib ]]; then
  PV_HOURLY_MODEL_PATH=models/pv_hourly_model_cs4.joblib \
    "$PYTHON" mlops/forecast_pv.py --days 2 --top 5 --no-operational-adjust --run-label cs4_shadow
else
  echo "Brak models/pv_hourly_model_cs4.joblib — najpierw trening."
  exit 1
fi

echo
echo "Gotowe. Produkcja nadal: models/pv_hourly_model.joblib (16 cech)."
echo "CS4 shadow: models/pv_hourly_model_cs4.joblib"
echo "Raport tygodnia: docs/UPDATE_2026-07-26_cs4-dual.md"
