"""
Pobiera dane pogodowe z Open-Meteo i zapisuje do weather_data.

Wymaga w .env: WEATHER_LAT, WEATHER_LON (współrzędne instalacji — bez adresu).

Uruchomienie:
    source venv/bin/activate
    python scripts/fetch_weather.py

Opcjonalnie w .env:
    WEATHER_START_DATE=2025-04-21
    WEATHER_END_DATE=2026-04-30   (domyślnie: dziś)
    WEATHER_FORECAST_DAYS=3       (prognoza na kolejne dni)
    OPENMETEO_MODEL=icon_seamless (lepsze chmury; domyślnie best_match)
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.household_context import WEATHER_DATA_START
from src.data.weather_api import (
    DEFAULT_OPENMETEO_MODEL,
    OpenMeteoClient,
    filter_forecast_preserve_archive,
    get_ensemble_forecast,
    save_weather_to_db,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')


def main():
    client = OpenMeteoClient.from_env()

    start = os.getenv('WEATHER_START_DATE', WEATHER_DATA_START.isoformat())
    end = os.getenv('WEATHER_END_DATE', date.today().isoformat())
    forecast_days = int(os.getenv('WEATHER_FORECAST_DAYS', '3'))
    
    # ENSEMBLE: ICON+UKMO (E1.3)
    use_ensemble = os.getenv('WEATHER_ENSEMBLE_UKMO', '0') == '1'
    
    if use_ensemble:
        model_label = 'ENSEMBLE (icon+ukmo)'
    else:
        model_label = client.model or DEFAULT_OPENMETEO_MODEL

    print('=' * 70)
    print('Open-Meteo → weather_data')
    print(f'Lokalizacja: {client.location_label} ({client.latitude}, {client.longitude})')
    print(f'Model:      {model_label}')
    print(f'Historia:   {start} – {end}')
    print('=' * 70)

    hist = client.fetch_archive(start, end)
    n_hist = save_weather_to_db(hist, DB_PATH)
    print(f'✅ Archiwum: {len(hist)} godzin → zapisano {n_hist} rekordów')

    # Prognoza: ensemble lub single model
    if use_ensemble:
        fc = get_ensemble_forecast(
            latitude=client.latitude,
            longitude=client.longitude,
            forecast_days=forecast_days,
        )
    else:
        fc = client.fetch_forecast(forecast_days)
    
    fc = filter_forecast_preserve_archive(fc)
    n_fc = save_weather_to_db(fc, DB_PATH)
    print(f'✅ Prognoza ({forecast_days} dni): {len(fc)} godzin → zapisano {n_fc} rekordów')

    print('\n💡 Walidacja vs FoxESS:')
    print('   python scripts/validate_weather_pv.py')
    print('   python scripts/fetch_imgw_snow.py   # IMGW pokrywa śnieżna (stacja)')


if __name__ == '__main__':
    main()
