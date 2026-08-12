#!/usr/bin/env bash
# Uruchom aplikację w iOS Simulatorze z live-reload (proces zostaje w tle).
# Wymaga: Xcode, API na http://127.0.0.1:8000 (docker compose up -d db api)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${MOBILE_DEV_PORT:-8100}"
HOST="${MOBILE_DEV_HOST:-127.0.0.1}"
TARGET="${IOS_SIMULATOR_TARGET:-}"

echo "== Smart Energy — iOS Simulator =="
open -a Simulator 2>/dev/null || true

if ! curl -sf "http://127.0.0.1:8000/ready" >/dev/null; then
  echo "⚠️  API nie odpowiada na :8000 — uruchom: docker compose up -d db api"
fi

echo "→ build + sync…"
npm run build:sim
npx cap sync ios

# Zatrzymaj poprzednie instancje (ten sam port / ten sam projekt)
pkill -f "ng serve.*--port ${PORT}" 2>/dev/null || true
pkill -f "cap run ios.*--port ${PORT}" 2>/dev/null || true
sleep 1

echo "→ dev server :${PORT} (tło, utrzymany)…"
nohup npm start -- --host "${HOST}" --port "${PORT}" --disable-host-check \
  >> /tmp/smart-energy-mobile-serve.log 2>&1 &
echo $! > /tmp/smart-energy-mobile-serve.pid

for _ in $(seq 1 45); do
  if curl -sf "http://${HOST}:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -sf "http://${HOST}:${PORT}/" >/dev/null 2>&1; then
  echo "❌ Dev server nie wystartował — sprawdź /tmp/smart-energy-mobile-serve.log"
  exit 1
fi

# Live-reload URL w ios/App/App/capacitor.config.json
node -e "
const fs=require('fs');
const p='ios/App/App/capacitor.config.json';
const j=JSON.parse(fs.readFileSync(p,'utf8'));
j.server={url:'http://${HOST}:${PORT}'};
fs.writeFileSync(p, JSON.stringify(j,null,'\t'));
"

CAP_ARGS=(run ios --no-sync)
if [[ -n "${TARGET}" ]]; then
  CAP_ARGS+=(--target "${TARGET}")
else
  BOOTED=$(xcrun simctl list devices booted | awk -F '[()]' '/Booted/ {print $2; exit}')
  if [[ -n "${BOOTED}" ]]; then
    CAP_ARGS+=(--target "${BOOTED}")
    echo "→ simulator: ${BOOTED}"
  fi
fi

echo "→ instalacja natywna (cap run, jednorazowo)…"
if ! npx cap "${CAP_ARGS[@]}" >> /tmp/smart-energy-cap-ios.log 2>&1; then
  echo "⚠️  cap run zwrócił błąd — sprawdź /tmp/smart-energy-cap-ios.log"
fi

echo "→ uruchamiam aplikację…"
xcrun simctl launch "${BOOTED:-booted}" com.smartenergy.app >/dev/null

echo ""
echo "✅ Simulator uruchomiony (dev server w tle — nie zamknie się sam)"
echo "   App dev:  http://${HOST}:${PORT}"
echo "   Symulator → Więcej → Symulator rachunku"
echo "   Logi:     tail -f /tmp/smart-energy-mobile-serve.log"
echo "   Stop:     kill \$(cat /tmp/smart-energy-mobile-serve.pid 2>/dev/null)"
