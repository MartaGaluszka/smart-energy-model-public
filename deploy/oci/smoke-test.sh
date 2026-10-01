#!/usr/bin/env bash
# Smoke test publicznego API (HTTPS nip.io lub lokalny tunnel).
# Użycie: ./deploy/oci/smoke-test.sh https://130-61-12-34.nip.io
set -euo pipefail

BASE="${1:?Podaj bazowy URL, np. https://130-61-12-34.nip.io}"
BASE="${BASE%/}"

echo "GET ${BASE}/health"
curl -fsS --max-time 30 "${BASE}/health" | head -c 400
echo
echo "GET ${BASE}/ready"
curl -fsS --max-time 30 "${BASE}/ready" | head -c 400
echo
echo "GET ${BASE}/docs →"
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "${BASE}/docs")"
echo "HTTP ${code}"
[[ "$code" == "200" ]] || exit 1
echo "OK smoke"
