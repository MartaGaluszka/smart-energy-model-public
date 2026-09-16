#!/usr/bin/env bash
# 04:15: nie usypiaj + sam odpal train (nd) i daily 05:00.
# Osobny job calendar 05:00 bywa pusty (flock/DNS). Ten proces 12.09 WYSTSTARTOWAŁ.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "${MLOPS_CAFFEINATED:-0}" != 1 ]; then
  export MLOPS_CAFFEINATED=1
  echo "=== morning-hold | $(date '+%Y-%m-%d %H:%M:%S') — caffeinate + run poranny ==="
  exec /usr/bin/caffeinate -s "$0" "$@"
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_network.sh"

wait_until() {
  local hm="$1"
  local today target now
  today="$(date '+%Y-%m-%d')"
  target="$(date -j -f '%Y-%m-%d %H:%M:%S' "${today} ${hm}:00" '+%s')"
  now="$(date '+%s')"
  if [ "${now}" -lt "${target}" ]; then
    echo "--- czekam do ${hm} ($((target - now))s) ---"
    sleep $((target - now))
  fi
}

# Niedziela: weekly przed Poranną (ten sam proces, nie drugi calendar).
if [ "$(date '+%w')" = "0" ]; then
  wait_until "04:30"
  echo "--- morning-hold: weekly train ---"
  mlops_wait_for_network 12
  "${PROJECT_ROOT}/mlops/train_dual_weekly.sh" || echo "⚠️  train z morning-hold — błąd $?" >&2
fi

wait_until "05:00"
echo "--- morning-hold: daily (Poranna) ---"
mlops_wait_for_network 12
"${PROJECT_ROOT}/mlops/daily_workflow.sh" || echo "⚠️  daily z morning-hold — błąd $?" >&2

echo "=== morning-hold done | $(date '+%Y-%m-%d %H:%M:%S') ==="
