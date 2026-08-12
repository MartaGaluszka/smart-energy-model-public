#!/usr/bin/env bash
# =============================================================================
# Smart Home PV — weryfikacja + uruchomienie workflow (prezentacja / demo)
#
# Sprawdza środowisko, API FoxESS, świeżość prognozy i zależności,
# następnie uruchamia daily_workflow.sh (sync + predykcja).
#
# Użycie:
#   ./mlops/verify_and_run.sh              # pełny run
#   ./mlops/verify_and_run.sh --check-only   # tylko diagnostyka (bez sync)
# =============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/cron_debug.log"
FORECAST_FILE="${PROJECT_ROOT}/data/processed/pv_forecast.csv"
MODEL_FILE="${PROJECT_ROOT}/models/pv_hourly_model.joblib"
CHECK_ONLY=false

# Kolory (wyłączane gdy brak TTY)
if [[ -t 1 ]]; then
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[1;33m'
  C_RED='\033[0;31m'
  C_CYAN='\033[0;36m'
  C_BOLD='\033[1m'
  C_RESET='\033[0m'
else
  C_GREEN='' C_YELLOW='' C_RED='' C_CYAN='' C_BOLD='' C_RESET=''
fi

for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=true ;;
    -h|--help)
      echo "Użycie: $0 [--check-only]"
      echo "  --check-only   Tylko weryfikacja (bez daily_workflow.sh)"
      exit 0
      ;;
    *)
      echo "Nieznany argument: $arg (użyj --help)"
      exit 1
      ;;
  esac
done

mkdir -p "$LOG_DIR"

log_line() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] ${msg}" >> "$LOG_FILE"
}

say() {
  echo -e "$1"
  log_line "$(echo -e "$1" | sed 's/\x1b\[[0-9;]*m//g')"
}

say_ok()   { say "${C_GREEN}  ✓ OK${C_RESET} — $1"; }
say_warn() { say "${C_YELLOW}  ⚠ UWAGA${C_RESET} — $1"; }
say_fail() { say "${C_RED}  ✗ BŁĄD${C_RESET} — $1"; }
say_step() { say "${C_CYAN}${C_BOLD}▶ $1${C_RESET}"; }

die() {
  say_fail "$1"
  log_line "ABORT: $1"
  exit "${2:-1}"
}

# ---------------------------------------------------------------------------
# 1. Katalog projektu
# ---------------------------------------------------------------------------
check_project() {
  say_step "Sprawdzam katalog projektu..."

  local markers=(
    "${PROJECT_ROOT}/mlops/daily_workflow.sh"
    "${PROJECT_ROOT}/data/energy_model.db"
    "${PROJECT_ROOT}/requirements.txt"
  )
  for f in "${markers[@]}"; do
    [[ -f "$f" ]] || die "Brak pliku projektu: $f (czy to smart-energy-model?)"
  done

  if [[ "$(pwd -P)" != "$(cd "$PROJECT_ROOT" && pwd -P)" ]]; then
    say_warn "Nie jesteś w katalogu projektu — przechodzę do: ${PROJECT_ROOT}"
    cd "$PROJECT_ROOT"
  fi

  say_ok "Katalog projektu: ${PROJECT_ROOT}"
}

# ---------------------------------------------------------------------------
# 2. Środowisko wirtualne
# ---------------------------------------------------------------------------
check_venv() {
  say_step "Sprawdzam środowisko Python (venv)..."

  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/mlops/_venv.sh" || die "Brak venv — uruchom: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"

  export VERIFY_PROJECT_ROOT="${PROJECT_ROOT}"
  say_ok "Python: ${PYTHON}"
  if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    say_ok "Plik .env załadowany"
  else
    say_warn "Brak .env — API FoxESS może nie działać"
  fi
}

# ---------------------------------------------------------------------------
# 3. Zależności Python
# ---------------------------------------------------------------------------
check_dependencies() {
  say_step "Sprawdzam zależności Python..."

  "$PYTHON" - <<'PY' || die "Brakujące pakiety — uruchom: pip install -r requirements.txt"
import importlib
import os
import sys
from pathlib import Path

# load_dotenv() z heredoc wymaga jawnej ścieżki
from dotenv import load_dotenv
load_dotenv(Path(os.environ["VERIFY_PROJECT_ROOT"]) / ".env")

required = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("joblib", "joblib"),
    ("dotenv", "python-dotenv"),
    ("foxesscloud", "foxesscloud"),
    ("astral", "astral"),
]

missing = []
for mod, pkg in required:
    try:
        importlib.import_module(mod)
    except ImportError:
        missing.append(pkg)

if missing:
    print("Brakuje:", ", ".join(missing))
    sys.exit(1)
print("Wszystkie pakiety dostępne")
PY

  say_ok "Zależności Python zainstalowane"
}

# ---------------------------------------------------------------------------
# 4. Połączenie z API FoxESS
# ---------------------------------------------------------------------------
check_api() {
  say_step "Sprawdzam API FoxESS..."

  "$PYTHON" - <<'PY' || die "Połączenie z FoxESS nieudane — sprawdź FOXESS_API_KEY w .env"
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv(Path(os.environ["VERIFY_PROJECT_ROOT"]) / ".env")

api_key = (os.getenv("FOXESS_API_KEY") or os.getenv("FOXESS_TOKEN") or "").strip().strip('"').strip("'")
if not api_key or api_key.startswith("your_"):
    print("Brak FOXESS_API_KEY w .env")
    sys.exit(1)

import foxesscloud.openapi as foxess

foxess.api_key = api_key
device_sn = os.getenv("FOXESS_DEVICE_SN")
if device_sn:
    foxess.device_sn = device_sn.strip().strip('"').strip("'")

response = foxess.signed_post(path="/op/v0/device/list", body={"pageSize": 5, "currentPage": 1})
if response.status_code == 401:
    print("401 Unauthorized — niepoprawny klucz API")
    sys.exit(1)
if response.status_code != 200:
    print(f"HTTP {response.status_code}: {response.reason}")
    sys.exit(1)

devices = (response.json().get("result") or {}).get("data") or []
print(f"Połączenie OK — urządzeń na koncie: {len(devices)}")
PY

  say_ok "API FoxESS odpowiada"
}

# ---------------------------------------------------------------------------
# 5. Świeżość prognozy + model
# ---------------------------------------------------------------------------
check_forecast() {
  say_step "Sprawdzam prognozę PV..."

  [[ -f "$MODEL_FILE" ]] || say_warn "Brak modelu: ${MODEL_FILE} (forecast_pv.py wytrenuje przy pierwszym uruchomieniu)"

  if [[ ! -f "$FORECAST_FILE" ]]; then
    say_warn "Brak pliku prognozy — zostanie utworzony po uruchomieniu workflow"
    return 0
  fi

  local forecast_date file_age_hours today
  today="$(date '+%Y-%m-%d')"
  forecast_date="$(date -r "$FORECAST_FILE" '+%Y-%m-%d' 2>/dev/null || stat -f '%Sm' -t '%Y-%m-%d' "$FORECAST_FILE")"
  file_age_hours=$(( ( $(date +%s) - $(stat -f '%m' "$FORECAST_FILE") ) / 3600 ))

  if [[ "$forecast_date" == "$today" ]]; then
    say_ok "Prognoza świeża (z dzisiaj, ${file_age_hours}h temu): ${FORECAST_FILE}"
  else
    say_warn "Prognoza nieaktualna (ostatnia: ${forecast_date}, dziś: ${today}) — workflow ją odświeży"
  fi
}

# ---------------------------------------------------------------------------
# 6. Uruchomienie workflow
# ---------------------------------------------------------------------------
run_workflow() {
  say_step "Uruchamiam predykcję (daily_workflow.sh)..."
  echo ""

  local attempt max_attempts=2
  max_attempts=2

  for attempt in $(seq 1 "$max_attempts"); do
    if [[ "$attempt" -gt 1 ]]; then
      say_warn "Retry ${attempt}/${max_attempts} — ponawiam workflow za 5 s..."
      sleep 5
    fi

    if bash "${PROJECT_ROOT}/mlops/daily_workflow.sh" 2>&1 | tee -a "$LOG_FILE"; then
      echo ""
      say_ok "Workflow zakończony pomyślnie"
      if [[ -f "$FORECAST_FILE" ]]; then
        say_ok "Nowa prognoza: ${FORECAST_FILE} ($(date -r "$FORECAST_FILE" '+%Y-%m-%d %H:%M' 2>/dev/null || stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$FORECAST_FILE"))"
      fi
      return 0
    fi

    log_line "Workflow attempt ${attempt} failed"
  done

  die "Workflow nie powiódł się po ${max_attempts} próbach — szczegóły: ${LOG_FILE}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  say ""
  say "${C_BOLD}══════════════════════════════════════════════════════════════${C_RESET}"
  say "${C_BOLD}  Smart Home PV — verify_and_run (demo / prezentacja)${C_RESET}"
  say "${C_BOLD}══════════════════════════════════════════════════════════════${C_RESET}"
  say "  Log: ${LOG_FILE}"
  say ""

  check_project
  check_venv
  check_dependencies
  check_api
  check_forecast

  if [[ "$CHECK_ONLY" == true ]]; then
    say ""
    say_ok "Weryfikacja zakończona (--check-only, workflow pominięty)"
    exit 0
  fi

  run_workflow

  say ""
  say "${C_BOLD}══════════════════════════════════════════════════════════════${C_RESET}"
  say "${C_GREEN}${C_BOLD}  GOTOWE — system gotowy do prezentacji${C_RESET}"
  say "${C_BOLD}══════════════════════════════════════════════════════════════${C_RESET}"
  say ""
}

main "$@"
