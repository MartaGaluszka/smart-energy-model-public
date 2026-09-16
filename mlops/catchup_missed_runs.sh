#!/usr/bin/env bash
# Nadrabianie: sen Maca albo urwanie DNS. launchd woła /bin/bash 3.2 — bez mapfile/flock.
# Zawsze exit 0 — closeout ma iść dalej.

set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

HISTORY="${PROJECT_ROOT}/data/processed/forecasts/forecast_history.csv"
TRAIN_MARKER="${PROJECT_ROOT}/logs/.weekly_train_ok"
TODAY="$(date '+%Y-%m-%d')"
DAILY_STATE="${PROJECT_ROOT}/logs/.catchup_daily_${TODAY}"

JOBS_RAW="$("$PYTHON" -m src.ops.catchup_needed \
  --history "${HISTORY}" \
  --train-marker "${TRAIN_MARKER}" \
  --daily-state "${DAILY_STATE}" 2>/dev/null || true)"

if [ -z "${JOBS_RAW}" ]; then
  exit 0
fi

echo ""
echo "=== Catch-up | $(date '+%Y-%m-%d %H:%M:%S') | ${JOBS_RAW} ==="

# train / daily — pojedyncze słowa, pętla bez mapfile
for job in ${JOBS_RAW}; do
  case "${job}" in
    train)
      echo "--- Catch-up: weekly train ---"
      if "${PROJECT_ROOT}/mlops/train_dual_weekly.sh" >> "${PROJECT_ROOT}/logs/train.log" 2>&1; then
        echo "✓ Catch-up train — OK"
      else
        echo "⚠️  Catch-up train — błąd (kod $?) — spróbuję przy następnym ticku" >&2
      fi
      ;;
    daily)
      echo "--- Catch-up: daily (Poranna) ---"
      prev=0
      if [ -f "${DAILY_STATE}" ]; then
        prev="$(awk '{print $1}' "${DAILY_STATE}" 2>/dev/null || echo 0)"
      fi
      echo "$((prev + 1)) $(date '+%Y-%m-%dT%H:%M:%S')" > "${DAILY_STATE}"
      if "${PROJECT_ROOT}/mlops/daily_workflow.sh"; then
        echo "✓ Catch-up daily — OK"
      else
        echo "⚠️  Catch-up daily — błąd (kod $?) — max 4 próby, co ≥20 min" >&2
      fi
      ;;
  esac
done

exit 0
