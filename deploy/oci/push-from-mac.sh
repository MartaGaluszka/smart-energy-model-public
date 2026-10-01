#!/usr/bin/env bash
# Z Maca: wgraj kod + dane na VM OCI i podnieś stack (Caddy + API + Postgres).
#
# Użycie:
#   export OCI_SSH="ubuntu@130.61.12.34"          # user@public-IP
#   export OCI_PUBLIC_IP="130.61.12.34"            # do nip.io
#   export OCI_SSH_KEY="$HOME/.ssh/oci_key"        # opcjonalnie
#   ./deploy/oci/push-from-mac.sh
#
# Wymaga: lokalnego .env skopiowanego wcześniej LUB wygeneruje deploy/oci/.env na VM
# z PUBLIC_HOST z OCI_PUBLIC_IP (hasła musisz uzupełnić ręcznie przy pierwszym razie).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OCI_SSH="${OCI_SSH:?Ustaw OCI_SSH=ubuntu@PUBLIC_IP}"
OCI_PUBLIC_IP="${OCI_PUBLIC_IP:?Ustaw OCI_PUBLIC_IP=x.x.x.x}"
REMOTE_DIR="${OCI_REMOTE_DIR:-/home/ubuntu/smart-energy-model}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [[ -n "${OCI_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "$OCI_SSH_KEY")
fi
RSYNC_RSH="ssh ${SSH_OPTS[*]}"
export RSYNC_RSH

nip_host() {
  echo "${1//./-}.nip.io"
}

PUBLIC_HOST="$(nip_host "$OCI_PUBLIC_IP")"
echo "→ Host HTTPS: https://${PUBLIC_HOST}"
echo "→ SSH: ${OCI_SSH}  remote: ${REMOTE_DIR}"

ssh "${SSH_OPTS[@]}" "$OCI_SSH" "mkdir -p '${REMOTE_DIR}/data' '${REMOTE_DIR}/models' '${REMOTE_DIR}/deploy/oci'"

echo "→ rsync kodu (bez venv/node_modules/.git dużych artefaktów)…"
rsync -az --delete \
  --exclude '.git/' \
  --exclude 'venv/' \
  --exclude 'mobile/node_modules/' \
  --exclude 'mobile/www/' \
  --exclude 'mobile/ios/App/Pods/' \
  --exclude 'data/*.db' \
  --exclude 'data/*.db-*' \
  --exclude 'models/*.joblib' \
  --exclude '.env' \
  --exclude 'deploy/oci/.env' \
  "$ROOT/" "${OCI_SSH}:${REMOTE_DIR}/"

echo "→ rsync SQLite + model produkcyjny…"
if [[ -f "$ROOT/data/energy_model.db" ]]; then
  rsync -az "$ROOT/data/energy_model.db" "${OCI_SSH}:${REMOTE_DIR}/data/energy_model.db"
fi
if [[ -f "$ROOT/models/pv_hourly_model.joblib" ]]; then
  rsync -az \
    "$ROOT/models/pv_hourly_model.joblib" \
    "${OCI_SSH}:${REMOTE_DIR}/models/pv_hourly_model.joblib"
fi

echo "→ upewnij się, że jest deploy/oci/.env na VM…"
ssh "${SSH_OPTS[@]}" "$OCI_SSH" bash -s <<EOF
set -euo pipefail
cd '${REMOTE_DIR}/deploy/oci'
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "UTWORZONO .env z przykładu — UZUPEŁNIJ JWT_SECRET, POSTGRES_PASSWORD, FOXESS_API_KEY!"
fi
# Zawsze synchronizuj PUBLIC_HOST z aktualnym IP
sed -i.bak "s|^PUBLIC_HOST=.*|PUBLIC_HOST=${PUBLIC_HOST}|" .env
grep -q '^PUBLIC_HOST=' .env || echo "PUBLIC_HOST=${PUBLIC_HOST}" >> .env
chmod +x bootstrap-vm.sh smoke-test.sh push-from-mac.sh 2>/dev/null || true
EOF

echo "→ docker compose up --build…"
ssh "${SSH_OPTS[@]}" "$OCI_SSH" bash -s <<EOF
set -euo pipefail
cd '${REMOTE_DIR}/deploy/oci'
if ! command -v docker >/dev/null 2>&1; then
  echo "Brak Dockera — uruchom: sudo bash ${REMOTE_DIR}/deploy/oci/bootstrap-vm.sh"
  exit 1
fi
docker compose up -d --build
docker compose ps
EOF

echo "→ smoke HTTPS (poczekaj ~15s na cert)…"
sleep 15
bash "$ROOT/deploy/oci/smoke-test.sh" "https://${PUBLIC_HOST}" || true

echo "Gotowe. Docs: https://${PUBLIC_HOST}/docs  Ready: https://${PUBLIC_HOST}/ready"
echo "Mobile prod: ustaw apiBaseUrl na https://${PUBLIC_HOST} (environment.prod.ts)."
