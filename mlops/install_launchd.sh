#!/usr/bin/env bash
# Automatyzacja PV przez launchd (zalecane na macOS zamiast crontab).
#
# Użycie:
#   ./mlops/install_launchd.sh           # instalacja
#   ./mlops/install_launchd.sh --status  # status
#   ./mlops/install_launchd.sh --remove
#   ./mlops/install_launchd.sh --test-daily   # natychmiastowy test joba 5:00
#   ./mlops/install_launchd.sh --schedule-wake  # sudo: budź Maca 04:15 (przed train/daily)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHD_DIR="${HOME}/Library/LaunchAgents"
TEMPLATE_DIR="${PROJECT_ROOT}/config/launchd"
LOG_DIR="${PROJECT_ROOT}/logs"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

LABELS=(
  "pl.smart-energy-model.daily"
  "pl.smart-energy-model.midday"
  "pl.smart-energy-model.peak"
  "pl.smart-energy-model.evening"
  "pl.smart-energy-model.evening-dynamic"
  "pl.smart-energy-model.morning-hold"
  "pl.smart-energy-model.weekly-review"
  "pl.smart-energy-model.train"
)

usage() {
  echo "Użycie: $0 [--status|--remove|--test-daily|--schedule-wake]"
}

render_plist() {
  local src="$1"
  local dest="$2"
  sed "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" "${src}" > "${dest}"
}

unload_label() {
  local label="$1"
  launchctl bootout "${DOMAIN}/${label}" 2>/dev/null || true
}

load_label() {
  local plist="$1"
  launchctl bootstrap "${DOMAIN}" "${plist}"
  launchctl enable "${DOMAIN}/$(basename "${plist}" .plist)" 2>/dev/null || true
}

install_launchd() {
  mkdir -p "${LOG_DIR}" "${LAUNCHD_DIR}"
  chmod +x "${PROJECT_ROOT}/mlops/daily_workflow.sh" \
    "${PROJECT_ROOT}/mlops/midday_forecast.sh" \
    "${PROJECT_ROOT}/mlops/peak_arrival.sh" \
    "${PROJECT_ROOT}/mlops/evening_closeout.sh" \
    "${PROJECT_ROOT}/mlops/evening_closeout_dynamic.sh" \
    "${PROJECT_ROOT}/mlops/catchup_missed_runs.sh" \
    "${PROJECT_ROOT}/mlops/morning_hold.sh" \
    "${PROJECT_ROOT}/mlops/forecast_cs4_shadow.sh" \
    "${PROJECT_ROOT}/mlops/forecast_xgb_ts_shadow.sh" \
    "${PROJECT_ROOT}/mlops/train_dual_weekly.sh"

  for label in "${LABELS[@]}"; do
    unload_label "${label}"
  done

  for tpl in "${TEMPLATE_DIR}"/pl.smart-energy-model.*.plist; do
    local name
    name="$(basename "${tpl}")"
    render_plist "${tpl}" "${LAUNCHD_DIR}/${name}"
    load_label "${LAUNCHD_DIR}/${name}"
  done

  echo "✅ launchd zainstalowany (LaunchAgents):"
  for label in "${LABELS[@]}"; do
    echo "   • ${label}"
  done
  echo ""
  echo "Harmonogram (prod RF 16 + shadow CS4 + shadow XGB+TS):"
  echo "   05:00 codziennie  → daily_workflow.sh (16 + CS4 + XGB+TS)"
  echo "   12:00 codziennie  → midday_forecast.sh (16 + CS4 + XGB+TS)"
  echo "   16:00 codziennie  → peak_arrival.sh (16 + CS4 + XGB+TS)"
  echo "   co 10 min         → evening_closeout_dynamic.sh (closeout + catch-up daily/train po śnie/DNS)"
  echo "   22:42 codziennie  → evening_closeout.sh (siatka bezpieczeństwa, gdyby dynamiczny nie zadziałał)"
  echo "   04:15 codziennie  → morning_hold.sh (nie usypiaj + sam train 04:30 nd + daily 05:00)"
  echo "   10:00 sobota      → weekly_model_review.sh (MAPE × pogoda × model; przed retreningiem)"
  echo "   04:30 niedziela   → train_dual_weekly.sh (retrening 16 + CS4 + XGB+TS; przed daily 05:00)"
  echo ""
  echo "Budzenie śpiącego Maca (hasło admina): $0 --schedule-wake"
  echo "Logi: ${LOG_DIR}/cron.log"
  echo "Status: $0 --status"
}

remove_launchd() {
  for label in "${LABELS[@]}"; do
    unload_label "${label}"
    rm -f "${LAUNCHD_DIR}/${label}.plist"
  done
  echo "✅ Usunięto joby launchd smart-energy-model."
}

show_status() {
  echo "=== launchd status (smart-energy-model) ==="
  for label in "${LABELS[@]}"; do
    echo ""
    echo "--- ${label} ---"
    launchctl print "${DOMAIN}/${label}" 2>/dev/null | sed -n '1,12p' || echo "(nie załadowany)"
    if [[ -f "${LAUNCHD_DIR}/${label}.plist" ]]; then
      echo "plist: ${LAUNCHD_DIR}/${label}.plist"
    fi
  done
  echo ""
  echo "=== Pliki logów ==="
  ls -la "${LOG_DIR}/" 2>/dev/null || echo "brak logs/"
}

test_daily() {
  echo "▶ Test: uruchamiam daily_workflow (jak o 5:00)..."
  "${PROJECT_ROOT}/mlops/daily_workflow.sh" >> "${LOG_DIR}/cron.log" 2>&1
  echo "✅ OK — sprawdź: tail -30 ${LOG_DIR}/cron.log"
}

schedule_wake() {
  echo "Ustawiam powtarzane budzenie: codziennie 04:15 (przed train 04:30 i daily 05:00)."
  echo "Mac i tak usypia po 1 min bezczynności — bez tego job o 04:15 nie wstanie ze snu."
  sudo pmset repeat wakeorpoweron MTWRFSU 04:15:00
  echo ""
  echo "Opcjonalnie (zalecane na zasilaniu — ekran może gasnąć, system nie):"
  echo "  sudo pmset -c sleep 0"
  echo ""
  pmset -g sched
}

case "${1:-}" in
  --status) show_status ;;
  --remove) remove_launchd ;;
  --test-daily) test_daily ;;
  --schedule-wake) schedule_wake ;;
  --help|-h) usage ;;
  "") install_launchd ;;
  *) usage; exit 1 ;;
esac
