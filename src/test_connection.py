"""
Test połączenia z FoxEss Cloud Open API.

Wystarczy FOXESS_API_KEY w .env (private token z API Management, portal V1).
"""

import os
import json
import foxesscloud.openapi as foxess
from dotenv import load_dotenv

print("Rozpoczynam próbę połączenia z FoxESS Cloud (Open API)...")

load_dotenv()
api_key = (os.getenv("FOXESS_API_KEY") or os.getenv("FOXESS_TOKEN") or "").strip().strip('"').strip("'")

if not api_key or api_key.startswith("your_"):
    print("❌ Brak poprawnego FOXESS_API_KEY w pliku .env!")
    print("   Wygeneruj klucz: portal V1 → User Profile → API Management → Generate API key")
    print("   Dokumentacja: https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html")
    raise SystemExit(1)

foxess.api_key = api_key

device_sn = os.getenv("FOXESS_DEVICE_SN")
if device_sn:
    foxess.device_sn = device_sn.strip().strip('"').strip("'")

print(f"🔑 Klucz API: {api_key[:8]}...{api_key[-4:]} (długość: {len(api_key)})")

try:
    print("Próbuję pobrać listę urządzeń (/op/v0/device/list)...")
    response = foxess.signed_post(path="/op/v0/device/list", body={"pageSize": 100, "currentPage": 1})

    if response.status_code == 401:
        print("\n❌ Błąd 401 Unauthorized — serwer odrzucił klucz API")
        print("\nMożliwe przyczyny:")
        print("  1. Klucz niepoprawny lub wygasły (wygeneruj nowy w API Management)")
        print("  2. Klucz z niewłaściwego miejsca — potrzebny „private API key”, nie OAuth Client Secret")
        print("  3. Klucz wygenerowany na innym koncie niż instalacja")
        print("  4. Spacje/cudzysłowy w .env — użyj: FOXESS_API_KEY=klucz_bez_cudzysłowów")
        try:
            body = response.json()
            if body.get("errno") or body.get("msg"):
                print(f"\nOdpowiedź API: errno={body.get('errno')}, msg={body.get('msg')}")
        except Exception:
            pass
        raise SystemExit(1)

    if response.status_code != 200:
        print(f"\n❌ Błąd HTTP {response.status_code}: {response.reason}")
        try:
            print(f"   {response.json()}")
        except Exception:
            pass
        raise SystemExit(1)

    result = response.json().get("result") or {}
    devices = result.get("data") or []
    total = result.get("total", len(devices))

    if not devices:
        print("⚠️ Autoryzacja OK, ale na koncie nie ma urządzeń.")
        raise SystemExit(0)

    print(f"\n✅ SUKCES! Połączenie działa. Urządzeń: {total}")
    for d in devices[:5]:
        print(f"   • SN: {d.get('deviceSN')}  |  Typ: {d.get('deviceType')}")

    device = foxess.get_device()
    if device:
        print(f"\n⚡ Instalacja: {device.get('plantName', '—')}")

except SystemExit:
    raise
except Exception as e:
    print(f"\n❌ Błąd połączenia: {e}")
    raise SystemExit(1)
