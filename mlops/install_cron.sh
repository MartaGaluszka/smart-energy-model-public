#!/usr/bin/env bash
# Instalacja wpisów CRON dla Smart Home PV (macOS / Linux).
#
# Użycie:
#   ./mlops/install_cron.sh          # instalacja
#   ./mlops/install_cron.sh --status # podgląd bez zmian
#   ./mlops/install_cron.sh --remove # usuń wpisy projektu

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/logs/cron.log"
TRAIN_LOG="${PROJECT_ROOT}/logs/train.log"
MARKER="smart-energy-model"

DAILY="${PROJECT_ROOT}/mlops/daily_workflow.sh"
MIDDAY="${PROJECT_ROOT}/mlops/midday_forecast.sh"
PEAK="${PROJECT_ROOT}/mlops/peak_arrival.sh"
EVENING="${PROJECT_ROOT}/mlops/evening_closeout.sh"
TRAIN_CMD="cd ${PROJECT_ROOT} && ${PROJECT_ROOT}/mlops/train_dual_weekly.sh"

CRON_DAILY="0 5 * * * ${DAILY} >> ${LOG_FILE} 2>&1  # ${MARKER}: sync + prognoza 3 dni"
CRON_MIDDAY="0 12 * * * ${MIDDAY} >> ${LOG_FILE} 2>&1  # ${MARKER}: odświeżenie + bateria 13–15"
CRON_PEAK="0 16 * * * ${PEAK} >> ${LOG_FILE} 2>&1  # ${MARKER}: peak arrival 16–22"
CRON_EVENING="42 22 * * * ${EVENING} >> ${LOG_FILE} 2>&1  # ${MARKER}: closeout FoxESS + walidacja"
CRON_TRAIN="0 5 * * 0 ${TRAIN_CMD} >> ${TRAIN_LOG} 2>&1  # ${MARKER}: retrening niedziela"

usage() {
  echo "Użycie: $0 [--status|--remove]"
}

filter_project_cron() {
  crontab -l 2>/dev/null | grep -v "${MARKER}" || true
}

install_cron() {
  mkdir -p "${PROJECT_ROOT}/logs"
  chmod +x "${DAILY}" "${MIDDAY}" "${PEAK}" "${EVENING}"

  local existing
  existing="$(crontab -l 2>/dev/null || true)"
  if echo "${existing}" | grep -q "${MARKER}"; then
    echo "⚠️  Wpisy ${MARKER} już są w crontab — pomijam duplikaty."
    echo ""
    crontab -l | grep "${MARKER}" || true
    return 0
  fi

  {
    filter_project_cron
    echo ""
    echo "# ${MARKER} — automatyzacja PV (install_cron.sh $(date '+%Y-%m-%d'))"
    echo "${CRON_DAILY}"
    echo "${CRON_MIDDAY}"
    echo "${CRON_PEAK}"
    echo "${CRON_EVENING}"
    echo "${CRON_TRAIN}"
  } | crontab - || {
    echo "❌ crontab: Operation not permitted (macOS blokuje crontab w tym terminalu)." >&2
    echo "   Na Macu użyj: ./mlops/install_launchd.sh" >&2
    echo "   Albo: Ustawienia → Prywatność → Pełny dostęp do dysku → Terminal.app" >&2
    exit 1
  }

  echo "✅ CRON zainstalowany:"
  crontab -l | grep "${MARKER}" || true
  echo ""
  echo "Logi: ${LOG_FILE}"
  echo "Test ręczny: ${DAILY} >> ${LOG_FILE} 2>&1"
}

remove_cron() {
  if ! crontab -l >/dev/null 2>&1; then
    echo "Brak crontab użytkownika."
    return 0
  fi
  filter_project_cron | crontab -
  echo "✅ Usunięto wpisy ${MARKER} z crontab."
}

show_status() {
  echo "=== CRON status (${MARKER}) ==="
  if crontab -l >/dev/null 2>&1; then
    crontab -l | grep "${MARKER}" || echo "(brak wpisów projektu w crontab)"
  else
    echo "crontab: brak wpisów użytkownika"
  fi
  echo ""
  echo "=== Pliki logów ==="
  ls -la "${PROJECT_ROOT}/logs/" 2>/dev/null || echo "brak katalogu logs/"
  echo ""
  if [[ -f "${LOG_FILE}" ]]; then
    echo "=== Ostatnie 15 linii cron.log ==="
    tail -15 "${LOG_FILE}"
  else
    echo "cron.log jeszcze nie istnieje — uruchom: ${DAILY} >> ${LOG_FILE} 2>&1"
  fi
}

case "${1:-}" in
  --status) show_status ;;
  --remove) remove_cron ;;
  --help|-h) usage ;;
  "") install_cron ;;
  *) usage; exit 1 ;;
esac
