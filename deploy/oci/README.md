# Deploy API na Oracle Cloud (OCI) + HTTPS przez nip.io

Publiczny backend: **Postgres + FastAPI + Caddy** (Let’s Encrypt).  
MLOps / weekly train zostają na Macu; na VPS tylko API pod aplikację mobilną.

## Architektura

```text
iPhone / ng serve  --HTTPS-->  Caddy :443  -->  api :8000  -->  Postgres
                                              \-> SQLite data/energy_model.db
                                              \-> models/*.joblib
```

Alias DNS: **`https://<PUBLIC_IP_z_myślnikami>.nip.io`**  
Przykład: IP `130.61.12.34` → host `130-61-12-34.nip.io`.

## 1. Utwórz VM (konsola OCI) — jeśli jeszcze nie masz

1. **Compute → Create instance**
   - Image: Ubuntu 22.04 lub 24.04
   - Shape: Always Free **VM.Standard.A1.Flex** (Ampere ARM) — 1–2 OCPU, 6–12 GB RAM
   - Networking: **Assign public IPv4**
   - SSH key: wklej swój klucz publiczny
2. **Networking → Security List** (VCN subnety): ingress
   - TCP **22** (SSH; najlepiej ogranicz do swojego IP)
   - TCP **80**, **443** (Caddy / Let’s Encrypt)
   - **Nie** otwieraj 8000 ani 5432 na świat
3. Zapisz **publiczne IP**.

## 2. Bootstrap Dockera na VM

```bash
ssh ubuntu@PUBLIC_IP
# wgraj skrypt albo sklonuj repo, potem:
sudo bash deploy/oci/bootstrap-vm.sh
```

## 3. Sekrety na VM (`deploy/oci/.env`)

```bash
cd /path/to/smart-energy-model/deploy/oci
cp .env.example .env
# wygeneruj sekrety lokalnie i wklej:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Ustaw minimum:

| Zmienna | Opis |
|---------|------|
| `PUBLIC_HOST` | np. `130-61-12-34.nip.io` |
| `POSTGRES_PASSWORD` | silne hasło |
| `JWT_SECRET` | silny secret |
| `SECRETS_ENCRYPTION_KEY` | Fernet (trwały między restartami) |
| `FOXESS_API_KEY` | z portalu FoxESS |
| `WEATHER_LAT` / `WEATHER_LON` | tylko w `.env` na VM — **nie commitować** |

Plik `.env` jest w `.gitignore` — nie wrzucaj go do gita (ani publicznego, ani prywatnego z GPS/SN).

## 4. Deploy z Maca (zalecane)

Z katalogu repozytorium na Macu:

```bash
chmod +x deploy/oci/*.sh

export OCI_SSH="ubuntu@130.61.12.34"
export OCI_PUBLIC_IP="130.61.12.34"
# opcjonalnie:
# export OCI_SSH_KEY="$HOME/.ssh/id_rsa_oci"
# export OCI_REMOTE_DIR="/home/ubuntu/smart-energy-model"

./deploy/oci/push-from-mac.sh
```

Skrypt:

1. `rsync` kodu (bez `venv` / `node_modules`)
2. `rsync` `data/energy_model.db` + `models/pv_hourly_model.joblib`
3. ustawia `PUBLIC_HOST` w `deploy/oci/.env`
4. `docker compose up -d --build`
5. woła `smoke-test.sh` na `https://…nip.io`

Ręcznie na VM (alternatywa):

```bash
cd ~/smart-energy-model/deploy/oci
docker compose up -d --build
docker compose logs -f caddy api
```

## 5. Smoke test

```bash
./deploy/oci/smoke-test.sh https://130-61-12-34.nip.io
# oczekuj JSON z /health i /ready oraz HTTP 200 na /docs
```

Pierwszy certyfikat LE może zająć ~30–60 s — jeśli smoke failuje, `docker compose logs caddy` i powtórz.

## 6. Aplikacja mobilna (prod)

W [`mobile/src/environments/environment.prod.ts`](../../mobile/src/environments/environment.prod.ts) ustaw:

```ts
apiBaseUrl: 'https://130-61-12-34.nip.io',
```

(`YOUR_PUBLIC_IP_DASHED` → realny host z myślnikami.)

Build produkcyjny / TestFlight:

```bash
cd mobile
# po ustawieniu prawdziwego URL:
npx ionic build --prod   # lub ng build --configuration production
npx cap sync ios
```

Dev / Simulator (`build:sim`, `environment.ts`) nadal celuje w LAN / `127.0.0.1:8000` — bez zmian.

## 7. Checklist bezpieczeństwa

- [ ] Security List: tylko 22/80/443
- [ ] Silne `JWT_SECRET` / `POSTGRES_PASSWORD` / Fernet
- [ ] Brak GPS, SN, kluczy w commitach
- [ ] Postgres i API **bez** portów na `0.0.0.0` hosta
- [ ] Po zmianie IP zaktualizuj `PUBLIC_HOST` i `environment.prod.ts`

## Pliki w tym katalogu

| Plik | Rola |
|------|------|
| `docker-compose.yml` | db + api + caddy |
| `Caddyfile` | TLS + reverse_proxy → api:8000 |
| `.env.example` | szablon sekretów |
| `bootstrap-vm.sh` | instalacja Dockera na Ubuntu |
| `push-from-mac.sh` | rsync + compose up |
| `smoke-test.sh` | `/health` `/ready` `/docs` |

## 8. Gdy masz już publiczne IP

```bash
export OCI_SSH="ubuntu@TWOJE_IP"
export OCI_PUBLIC_IP="TWOJE_IP"
./deploy/oci/push-from-mac.sh
# potem w mobile/src/environments/environment.prod.ts:
# apiBaseUrl: 'https://TWOJE-IP-Z-MYŚLNIKAMI.nip.io'
./deploy/oci/smoke-test.sh "https://$(echo "$OCI_PUBLIC_IP" | tr . -).nip.io"
```

Live SSH/TLS na OCI uruchamia się dopiero z Twoim IP (skrypty powyżej są gotowe; bez IP nie da się wystawić certyfikatu nip.io).


- GitHub Actions deploy
- Cron FoxESS / weekly ML na OCI
- Własna domena (wystarczy zamienić `PUBLIC_HOST`)
