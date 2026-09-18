#!/usr/bin/env bash
# Sobota: tabela MAPE × pogoda × model — przed niedzielnym train_dual_weekly.sh
#
#   ./mlops/weekly_model_review.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"
export MPLBACKEND=Agg
export PYTHONPATH="${PROJECT_ROOT}"

echo ""
echo "=== Weekly model × weather review | $(date '+%Y-%m-%d %H:%M:%S') ==="

"$PYTHON" "${PROJECT_ROOT}/scripts/plots/build_weekly_model_weather_review.py" \
  --also-refresh-july-summary

echo "✓ Review: docs/images/ml/weekly_model_weather_review.md"
