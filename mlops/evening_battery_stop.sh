#!/usr/bin/env bash
# Timer stop FC (T6.2b). Launchd co 5 min, ale Fox Cloud tylko gdy minął stop_at,
# max BATTERY_STOP_FOX_MAX_ATTEMPTS (domyślnie 4) i nie częściej niż co 10 min.
#
# launchd: pl.smart-energy-model.evening-battery-stop

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

HOUR="$((10#$(date '+%H')))"
if [[ "${HOUR}" -lt 22 && "${HOUR}" -ge 6 ]]; then
  exit 0
fi

echo ""
echo "=== Evening battery STOP check | $(date '+%Y-%m-%d %H:%M:%S') ==="

if ! "$PYTHON" -c "from src.optimization.battery_control import control_enabled; import sys; sys.exit(0 if control_enabled() else 3)"; then
  exit 0
fi

"$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --stop-fc --apply
echo "=== Evening battery stop check OK ==="
