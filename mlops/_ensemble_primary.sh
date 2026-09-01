# shellcheck shell=bash
# Wspólna logika: ENSEMBLE_PRIMARY=1 → ICON+UKMO jako daily/midday/peak primary.
#
# Użycie (po `source mlops/_venv.sh` i `cd` do PROJECT_ROOT):
#   source mlops/_ensemble_primary.sh
#   run_pv_forecast_stack daily|midday|peak
#
# Gdy primary=ensemble:
#   - ICON → data/processed/pv_forecast_icon.csv (shadow)
#   - ensemble → data/processed/pv_forecast.csv (PRIMARY) + kopia pv_forecast_ensemble.csv
# Gdy primary=ICON (domyślnie historyczne):
#   - ICON → pv_forecast.csv
#   - ensemble → pv_forecast_ensemble.csv (shadow)

_ensemble_primary_enabled() {
  local v="${ENSEMBLE_PRIMARY:-0}"
  case "${v}" in
    1|true|yes|TRUE|YES) return 0 ;;
    *) return 1 ;;
  esac
}

# $1 = run label bazowy (daily|midday|peak)
run_pv_forecast_stack() {
  local label="${1:?run label}"
  local python_bin="${PYTHON:?PYTHON not set}"
  local root="${PROJECT_ROOT:?PROJECT_ROOT not set}"

  if _ensemble_primary_enabled; then
    echo "★ ENSEMBLE_PRIMARY=1 — ICON+UKMO = primary, ICON = shadow"
    # Jawne OpenMeteo-forecast — bez tego ENSEMBLE_PRIMARY=1 zaciągnąłby ensemble do shadow ICON.
    run_step "Prognoza ICON (shadow)" \
      env WEATHER_FORECAST_SOURCE_LIKE='OpenMeteo-forecast' \
      "$python_bin" "${root}/mlops/forecast_pv.py" --days 3 --top 5 \
        --run-label "${label}_icon" \
        --out data/processed/pv_forecast_icon.csv

    run_step "Prognoza CS4 (shadow)" \
      bash "${root}/mlops/forecast_cs4_shadow.sh" "${label}"

    run_step "Prognoza XGB+TS (shadow)" \
      bash "${root}/mlops/forecast_xgb_ts_shadow.sh" "${label}"

    run_step "Sync pogody ensemble ICON+UKMO" \
      "$python_bin" "${root}/mlops/sync_ensemble_weather.py"

    run_step "Prognoza PV PRIMARY (ensemble)" \
      env WEATHER_FORECAST_SOURCE_LIKE='%ensemble%' \
      "$python_bin" "${root}/mlops/forecast_pv.py" --days 3 --top 5 \
        --run-label "${label}" \
        --out data/processed/pv_forecast.csv

    cp -f data/processed/pv_forecast.csv data/processed/pv_forecast_ensemble.csv
    echo "✓ Skopiowano primary → pv_forecast_ensemble.csv (shadow mirror)"
  else
    run_step "Prognoza PV + harmonogram urządzeń (ICON primary)" \
      "$python_bin" "${root}/mlops/forecast_pv.py" --days 3 --top 5 --run-label "${label}"

    run_step "Prognoza CS4 (shadow)" \
      bash "${root}/mlops/forecast_cs4_shadow.sh" "${label}"

    run_step "Prognoza XGB+TS (shadow)" \
      bash "${root}/mlops/forecast_xgb_ts_shadow.sh" "${label}"

    run_step "Prognoza ensemble ICON+UKMO (shadow)" \
      bash "${root}/mlops/forecast_ensemble_shadow.sh" "${label}"
  fi

  run_step "Routing pick (shadow porównanie ENS vs CS4)" \
    "$python_bin" "${root}/scripts/analysis/routing_decision.py" --date today --also-next 2
}
