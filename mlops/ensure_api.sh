#!/usr/bin/env bash
# Po restarcie / braku prądu: podnieś Colima + Docker API, jeśli leży.
# Wołane z launchd (RunAtLoad + co 5 min). Zawsze exit 0.

set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

LOG="${PROJECT_ROOT}/logs/ensure_api.log"
stamp() { date '+%Y-%m-%d %H:%M:%S'; }

if curl -sf --max-time 3 "http://127.0.0.1:8000/ready" >/dev/null 2>&1; then
  exit 0
fi

echo "$(stamp) API down — próbuję podnieść…" >> "${LOG}"

# Colima (Docker na Macu bez Dockera Desktop)
if command -v colima >/dev/null 2>&1; then
  if ! colima status 2>/dev/null | grep -qi 'Running'; then
    echo "$(stamp) colima start…" >> "${LOG}"
    colima start >> "${LOG}" 2>&1 || true
    sleep 3
  fi
fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "$(stamp) docker compose up -d db api…" >> "${LOG}"
    docker compose up -d db api >> "${LOG}" 2>&1 || true
    for _ in $(seq 1 30); do
      if curl -sf --max-time 2 "http://127.0.0.1:8000/ready" >/dev/null 2>&1; then
        echo "$(stamp) API ready" >> "${LOG}"
        exit 0
      fi
      sleep 2
    done
    echo "$(stamp) API nadal down po compose" >> "${LOG}"
  else
    echo "$(stamp) docker daemon niedostępny" >> "${LOG}"
  fi
else
  echo "$(stamp) brak docker w PATH" >> "${LOG}"
fi

exit 0
