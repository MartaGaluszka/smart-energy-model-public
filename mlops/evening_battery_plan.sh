#!/usr/bin/env bash
# Plan B2 przed oknem 22:00 (~21:15): sugestie + dry-run sterowania (T4.26b).
#
# launchd: pl.smart-energy-model.evening-battery

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

run_soft() {
  local label="$1"
  shift
  echo ""
  echo "--- ${label} ---"
  if "$@"; then
    echo "✓ ${label} — OK"
  else
    local code=$?
    echo "⚠️  ${label} — błąd (kod ${code}) — kontynuuję" >&2
  fi
}

echo ""
echo "=== Evening battery plan (~21:15) | $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "ℹ️  Jedno wąskie odświeżenie SoC z Fox (dziś, 1 dzień) tuż przed decyzją; reszta z bazy."
# Nieświeży SoC = brak ForceCharge (case 09.11.2026: 57% z 18:50 vs ~14% o 22:00).
"$PYTHON" "${PROJECT_ROOT}/mlops/refresh_battery_soc.py" --max-age-min 10 \
  || echo "⚠️  refresh SoC nieudany — decyzja z bazy"

run_soft "Bateria — plan B2 (advisor evening)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/battery_advisor_report.py" --context evening

run_soft "Sugestie → notifications (evening)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/generate_battery_suggestions.py" --context evening

run_soft "Sterowanie — dry-run evening (bez odczytu falownika)" \
  "$PYTHON" "${PROJECT_ROOT}/mlops/foxess_control.py" --context evening --no-read-state

echo "=== Evening battery plan OK (advise-only) ==="
