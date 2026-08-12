#!/usr/bin/env bash
# Testy UKMO (kandydat) — NIE zmienia OPENMETEO_MODEL / produkcji.
#
# 1) Testy jednostkowe dual+UKMO (bez sieci)
# 2) Oneshot ICON vs UKMO (opad) — sieć Open-Meteo
# 3) Oneshot RF ICON vs UKMO (ten sam .joblib 16) — sieć
#
# Użycie:
#   ./scripts/analysis/run_ukmo_tests.sh
#   ./scripts/analysis/run_ukmo_tests.sh --unit-only
#   ./scripts/analysis/run_ukmo_tests.sh --start 2026-07-19 --end 2026-07-25

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT_ROOT="$ROOT"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"

UNIT_ONLY=0
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --unit-only) UNIT_ONLY=1 ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

echo "=== UKMO testy (produkcja = ICON + 16 cech; UKMO tylko oneshot) ==="

echo
echo "[1/3] Unit: dual 16+CS4 + resolve UKMO"
"$PYTHON" tests/test_dual_and_ukmo.py

if [[ "$UNIT_ONLY" -eq 1 ]]; then
  echo
  echo "Gotowe (--unit-only)."
  exit 0
fi

echo
echo "[2/3] Oneshot opad ICON vs UKMO"
"$PYTHON" scripts/analysis/oneshot_icon_vs_ukmo_precip.py "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

echo
echo "[3/3] Oneshot RF (16 cech) na pogodzie ICON vs UKMO"
"$PYTHON" scripts/analysis/oneshot_rf_icon_vs_ukmo.py "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

echo
echo "Gotowe. CSV: data/processed/oneshot_icon_vs_ukmo_*.csv / oneshot_rf_icon_vs_ukmo_*.csv"
echo "Produkcja nadal: OPENMETEO_MODEL=icon_seamless + 16 cech (+ CS4 shadow)."
