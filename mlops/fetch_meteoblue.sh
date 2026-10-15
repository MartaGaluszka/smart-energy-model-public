#!/usr/bin/env bash
# Poranny fetch Meteoblue Free API → weather_notes + stub.
# launchd: pl.smart-energy-model.meteoblue (domyślnie 08:00)
#
# Ręcznie:
#   ./mlops/fetch_meteoblue.sh
#   ./mlops/fetch_meteoblue.sh --days 3

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

exec "$PYTHON" "${PROJECT_ROOT}/scripts/weather/fetch_meteoblue.py" "$@"
