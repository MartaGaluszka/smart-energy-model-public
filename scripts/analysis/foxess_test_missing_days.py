"""
Szybki test API FoxESS — czy chmura ma dane za wybrany dzień (np. zima).

Użyj gdy limit API wrócił (brak 40402). Do pełnego importu lepiej:
    python src/data/foxess_fetch_all.py --from 2025-11-01 --to 2025-11-05 --delay 2

Uruchomienie:
    python scripts/foxess_test_missing_days.py
    python scripts/foxess_test_missing_days.py 2025-11-01 2025-11-03
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import foxesscloud.openapi as foxess
from dotenv import load_dotenv

load_dotenv()
api_key = (os.getenv('FOXESS_API_KEY') or os.getenv('FOXESS_TOKEN') or '').strip().strip('"').strip("'")
if not api_key:
    raise SystemExit('❌ Ustaw FOXESS_API_KEY w .env (nie tylko FOXESS_TOKEN)')

foxess.api_key = api_key
foxess.debug_setting = 99
sn = (os.getenv('FOXESS_DEVICE_SN') or '').strip()
if sn:
    foxess.device_sn = sn

if len(sys.argv) >= 3:
    start = date.fromisoformat(sys.argv[1])
    end = date.fromisoformat(sys.argv[2])
else:
    start = date(2025, 11, 1)
    end = date(2025, 11, 5)

print('Test pobierania historii FoxESS (Open API)')
device = foxess.get_device()
if not device:
    raise SystemExit(
        '❌ get_device() — brak odpowiedzi (limit 40402? odczekaj do resetu limitu, potem test_connection.py)'
    )
print(f'✅ Urządzenie: {foxess.device_sn}')

variables = ['generationPower', 'loadsPower', 'feedinPower', 'gridConsumptionPower', 'SoC']
day = start
while day <= end:
    d = day.isoformat()
    hist = foxess.get_history(
        time_span='day',
        d=d,
        v=variables,
        summary=0,
        plot=0,
    )
    rep = foxess.get_report(dimension='day', d=d, summary=1, plot=0)
    n_hist = sum(len(b.get('data') or []) for b in (hist or []))
    n_rep = len(rep or [])
    status = 'OK' if n_hist else 'PUSTO'
    print(f'  {d}: historia {n_hist} punktów, raport {"tak" if n_rep else "nie"} — {status}')
    day += timedelta(days=1)

print('\nJeśli wszystkie dni PUSTO — API działa, ale chmura nie ma historii za ten okres.')
print('Jeśli 40402 — nie testuj dalej, użyj foxess_fetch_all.py jutro w paczkach miesięcznych.')
