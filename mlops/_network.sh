# shellcheck shell=bash
# Czekaj na DNS po DarkWake / 04:15 — o 05:00 11.09 Open-Meteo padało na gaierror.

mlops_wait_for_network() {
  local i=1
  local max="${1:-12}"
  while [ "${i}" -le "${max}" ]; do
    if /usr/bin/python3 -c "import socket; socket.create_connection(('api.open-meteo.com', 443), 5).close()" 2>/dev/null; then
      echo "✓ Sieć OK (Open-Meteo, próba ${i})"
      return 0
    fi
    echo "⚠️  Brak sieci / DNS (${i}/${max}) — czekam 10s"
    sleep 10
    i=$((i + 1))
  done
  echo "⚠️  Sieć nadal nie odpowiada — kontynuuję (cache / retry w Pythonie)"
  return 0
}
