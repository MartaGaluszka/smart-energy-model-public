#!/usr/bin/env bash
# Top-up FC ~5:00 gdy pochmurny / mało PV + BATTERY_CONTROL_MORNING_CLOUDY=1 (T6.2c).
#
# launchd: pl.smart-energy-model.morning-battery-apply

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== Morning battery APPLY (pochmurny ~5:00) | $(date '+%Y-%m-%d %H:%M:%S') ==="

if ! "$PYTHON" -c "from src.optimization.battery_control import control_enabled; import sys; sys.exit(0 if control_enabled() else 3)"; then
  echo "ℹ️  BATTERY_CONTROL_ENABLED≠1 — dry-run"
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context morning --no-read-state
  exit 0
fi

if ! "$PYTHON" -c "from src.optimization.battery_control import morning_cloudy_apply_enabled; import sys; sys.exit(0 if morning_cloudy_apply_enabled() else 3)"; then
  echo "ℹ️  BATTERY_CONTROL_MORNING_CLOUDY≠1 — pomijam apply (dry-run)"
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context morning --no-read-state
  exit 0
fi

"$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context morning --apply --no-read-state
echo "=== Morning battery apply zakończone ==="
