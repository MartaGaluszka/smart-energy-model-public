#!/usr/bin/env bash
# RCEm z tabeli PSE → rcem_prices.
#
# launchd (11. dzień miesiąca, 23:05, także sobota, niedziela i święto):
#   pl.smart-energy-model.rcem
#
# Cena za miesiąc M jest publikowana 11. dnia M+1. Korekty PSE są możliwe
# przez 12 miesięcy od końca miesiąca, którego cena dotyczy — ten przebieg
# odświeża całe otwarte okno, nie tylko nową stawkę.
# 23:05 (nie 22:42): evening_closeout o 22:42 trzyma energy_model.db — 11.10.2026
# job RCEm wpadł w sqlite3.OperationalError: database is locked.
# Jeśli Mac spał o 23:05, launchd uruchamia job po wybudzeniu.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

echo ""
echo "=== RCEm PSE | $(date '+%Y-%m-%d %H:%M:%S') ==="
"$PYTHON" "${PROJECT_ROOT}/scripts/analysis/fetch_rcem.py" --fetch-pse
echo "=== RCEm PSE OK ==="
