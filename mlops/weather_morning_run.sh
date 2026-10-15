#!/usr/bin/env bash
# Poranny run pogodowy bez Cursor:
#   1) Meteoblue Free API → weather_notes
#   2) porównanie Accu (dashboard) × MB × ENS/ICON/CS4/XGB → markdown
#
# Przedtem: wpisz Accu w dashboardzie (Notatki pogodowe).
#
# Ręcznie:
#   ./mlops/weather_morning_run.sh
#   ./mlops/weather_morning_run.sh --skip-mb-fetch
#
# launchd 10:00: pl.smart-energy-model.meteoblue → ten skrypt

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

exec "$PYTHON" "${PROJECT_ROOT}/scripts/weather/weather_morning_run.py" "$@"
