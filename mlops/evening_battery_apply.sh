#!/usr/bin/env bash
# Start nocnego FC @22:00 gdy B2 triggered + BATTERY_CONTROL_ENABLED=1 (T6.2a).
#
# launchd: pl.smart-energy-model.evening-battery-apply

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== Evening battery APPLY (22:00) | $(date '+%Y-%m-%d %H:%M:%S') ==="

if ! "$PYTHON" -c "from src.optimization.battery_control import control_enabled; import sys; sys.exit(0 if control_enabled() else 3)"; then
  echo "ℹ️  BATTERY_CONTROL_ENABLED≠1 — tylko dry-run (bezpieczny domyślny tryb)"
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context evening
  exit 0
fi

"$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context evening --apply
echo "=== Evening battery apply zakończone ==="
