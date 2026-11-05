#!/usr/bin/env bash
# Bilans @~12:00 → ForceCharge 13–15 gdy luka energetyczna (BATTERY_CONTROL_PRE_CHEAP=1).
#
# launchd: opcjonalnie pl.smart-energy-model.midday-battery-apply (po midday_forecast)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== Midday battery APPLY (@12:00 bilans 13–15) | $(date '+%Y-%m-%d %H:%M:%S') ==="

if ! "$PYTHON" -c "from src.optimization.battery_control import control_enabled; import sys; sys.exit(0 if control_enabled() else 3)"; then
  echo "ℹ️  BATTERY_CONTROL_ENABLED≠1 — dry-run"
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context pre_cheap --no-read-state
  exit 0
fi

if ! "$PYTHON" -c "from src.optimization.battery_control import pre_cheap_apply_enabled; import sys; sys.exit(0 if pre_cheap_apply_enabled() else 3)"; then
  echo "ℹ️  BATTERY_CONTROL_PRE_CHEAP≠1 — pomijam apply (dry-run)"
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context pre_cheap --no-read-state
  exit 0
fi

"$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context pre_cheap --apply --no-read-state
echo "=== Midday battery apply zakończone ==="
