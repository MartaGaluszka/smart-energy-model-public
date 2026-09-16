# shellcheck shell=bash
# Blokada bez `flock` (Linux) — macOS /bin/bash 3.2 ma tylko mkdir.

mlops_acquire_lock() {
  local dir="${1:?lock dir}"
  local stale_s="${2:-10800}"
  if mkdir "${dir}" 2>/dev/null; then
    # shellcheck disable=SC2064
    trap "rmdir '${dir}' 2>/dev/null || true" EXIT
    return 0
  fi
  if [[ -d "${dir}" ]]; then
    local mtime now age
    mtime="$(stat -f %m "${dir}" 2>/dev/null || echo 0)"
    now="$(date +%s)"
    age=$((now - mtime))
    if [[ "${age}" -gt "${stale_s}" ]]; then
      rmdir "${dir}" 2>/dev/null || rm -rf "${dir}"
      if mkdir "${dir}" 2>/dev/null; then
        # shellcheck disable=SC2064
        trap "rmdir '${dir}' 2>/dev/null || true" EXIT
        return 0
      fi
    fi
  fi
  return 1
}
