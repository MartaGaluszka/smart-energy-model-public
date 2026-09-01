#!/usr/bin/env python3
"""Zapisuje prognozę ensemble ICON+UKMO do weather_data (osobny data_source).

Nie nadpisuje OpenMeteo-forecast (ICON). Używane przez shadow i przez ENSEMBLE_PRIMARY.
mlops/forecast_ensemble_shadow.sh przed prognozą PV shadow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')


def main() -> int:
    from src.data.weather_api import (
        OpenMeteoClient,
        filter_forecast_preserve_archive,
        get_ensemble_forecast,
        save_weather_to_db,
    )

    db_path = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    forecast_days = int(os.getenv('WEATHER_FORECAST_DAYS', '3'))
    client = OpenMeteoClient.from_env()

    print(f'Ensemble ICON+UKMO → {db_path} ({forecast_days} dni)')
    print(f'Lokalizacja: {client.location_label}')

    fc = get_ensemble_forecast(
        latitude=client.latitude,
        longitude=client.longitude,
        forecast_days=forecast_days,
    )
    fc = filter_forecast_preserve_archive(fc)
    n = save_weather_to_db(fc, db_path)
    print(f'✅ Ensemble forecast: {len(fc)} godzin → zapisano/upsert {n} rekordów')
    if 'data_source' in fc.columns and len(fc):
        print(f'   data_source: {fc["data_source"].iloc[0]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
