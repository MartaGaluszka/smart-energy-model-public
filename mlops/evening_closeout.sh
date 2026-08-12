#!/usr/bin/env bash
# Wieczorne domknięcie: FoxESS (pełna doba) + actual vs predicted.
#
# launchd (22:42):
#   pl.smart-energy-model.evening

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== Evening closeout | $(date '+%Y-%m-%d %H:%M:%S') ==="
"$PYTHON" "${PROJECT_ROOT}/mlops/evening_closeout.py"
echo "=== Evening closeout OK ==="
