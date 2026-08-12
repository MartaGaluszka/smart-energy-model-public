#!/usr/bin/env bash
# Niedzielny retrain: produkcja RF 16 + 2 shadowy (CS4, XGB+TS).
# Launchd: pl.smart-energy-model.train → ten skrypt.
#
# 1) production 16 → models/pv_hourly_model.joblib          (PRODUKCJA)
# 2) CS4 19       → models/pv_hourly_model_cs4.joblib       (shadow)
# 3) XGB+TS 24    → models/pv_hourly_model_xgb_ts.joblib    (shadow, WF v2)
#
# Prognozy: daily / midday / peak → RF 16 + CS4 + XGB+TS.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"
export MPLBACKEND=Agg

echo ""
echo "=== Weekly train (prod + 2 shadow) | $(date '+%Y-%m-%d %H:%M:%S') ==="

echo ""
echo "--- [1/3] Produkcja 16 cech → pv_hourly_model.joblib ---"
"$PYTHON" "${PROJECT_ROOT}/scripts/train/train_hourly_model_tuning.py" \
  --features production \
  --model-path models/pv_hourly_model.joblib

echo ""
echo "--- [2/3] CS4 (19 cech) → pv_hourly_model_cs4.joblib ---"
"$PYTHON" "${PROJECT_ROOT}/scripts/train/train_hourly_model_tuning.py" \
  --features cs4 \
  --model-path models/pv_hourly_model_cs4.joblib

echo ""
echo "--- [3/3] XGB+TS shadow → pv_hourly_model_xgb_ts.joblib ---"
"$PYTHON" "${PROJECT_ROOT}/scripts/train/train_xgb_ts_shadow.py" \
  --model-path models/pv_hourly_model_xgb_ts.joblib

echo ""
echo "✅ Train OK | produkcja RF 16 + shadow CS4 + shadow XGB+TS"
echo "   Primary:  models/pv_hourly_model.joblib"
echo "   CS4:      models/pv_hourly_model_cs4.joblib"
echo "   XGB+TS:   models/pv_hourly_model_xgb_ts.joblib"
