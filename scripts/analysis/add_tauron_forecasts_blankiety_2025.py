"""
Import prognozowanych faktur Tauron (zbiorczy blankiet sprzedaży).

Okres: 28.03.2025 – 28.02.2026 (6 blankietów dwumiesięcznych + pierwszy skrócony).
Źródło: Nr blankietu T/K1/0411004/25/1 … /25/6

Uruchomienie:
    cd /path/to/smart-energy-model
    source venv/bin/activate
    python scripts/add_tauron_forecasts_blankiety_2025.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.import_csv import EnergyDataImporter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prognozy z blankietu Tauron — Pobór [kWh], netto/brutto [zł], Do zapłaty [zł]
# Stref G12w na blankiecie nie ma → zone1/zone2 zostają NULL
TAURON_FORECASTS = [
    {
        'forecast_date': '2025-03-28',
        'forecast_period': '2025-03_2025-04',
        'forecast_total_kwh': 566.0,
        'forecast_energy_cost': 462.36,
        'forecast_total_cost': 568.69,
        'source': 'blankiet_prognoza_T/K1/0411004/25/1',
        'notes': (
            'Blankiet T/K1/0411004/25/1 | 28/03/2025–30/04/2025 | '
            'VAT 106,33 zł | Depozyt 125,44 zł | Do zapłaty 443,25 zł'
        ),
    },
    {
        'forecast_date': '2025-05-01',
        'forecast_period': '2025-05_2025-06',
        'forecast_total_kwh': 1016.0,
        'forecast_energy_cost': 801.22,
        'forecast_total_cost': 985.51,
        'source': 'blankiet_prognoza_T/K1/0411004/25/2',
        'notes': (
            'Blankiet T/K1/0411004/25/2 | 01/05/2025–30/06/2025 | '
            'VAT 184,29 zł | Depozyt 263,10 zł | Do zapłaty 722,41 zł'
        ),
    },
    {
        'forecast_date': '2025-07-01',
        'forecast_period': '2025-07_2025-08',
        'forecast_total_kwh': 1034.0,
        'forecast_energy_cost': 820.13,
        'forecast_total_cost': 1008.77,
        'source': 'blankiet_prognoza_T/K1/0411004/25/3',
        'notes': (
            'Blankiet T/K1/0411004/25/3 | 01/07/2025–31/08/2025 | '
            'VAT 188,64 zł | Depozyt 239,84 zł | Do zapłaty 768,93 zł'
        ),
    },
    {
        'forecast_date': '2025-09-01',
        'forecast_period': '2025-09_2025-10',
        'forecast_total_kwh': 1016.0,
        'forecast_energy_cost': 872.48,
        'forecast_total_cost': 1073.15,
        'source': 'blankiet_prognoza_T/K1/0411004/25/4',
        'notes': (
            'Blankiet T/K1/0411004/25/4 | 01/09/2025–31/10/2025 | '
            'VAT 200,67 zł | Depozyt 227,76 zł | Do zapłaty 845,39 zł'
        ),
    },
    {
        'forecast_date': '2025-11-01',
        'forecast_period': '2025-11_2025-12',
        'forecast_total_kwh': 1016.0,
        'forecast_energy_cost': 936.13,
        'forecast_total_cost': 1151.43,
        'source': 'blankiet_prognoza_T/K1/0411004/25/5',
        'notes': (
            'Blankiet T/K1/0411004/25/5 | 01/11/2025–31/12/2025 | '
            'VAT 215,30 zł | Depozyt 388,23 zł | Do zapłaty 763,20 zł'
        ),
    },
    {
        'forecast_date': '2026-01-01',
        'forecast_period': '2026-01_2026-02',
        'forecast_total_kwh': 984.0,
        'forecast_energy_cost': 916.52,
        'forecast_total_cost': 1127.34,
        'source': 'blankiet_prognoza_T/K1/0411004/25/6',
        'notes': (
            'Blankiet T/K1/0411004/25/6 | 01/01/2026–28/02/2026 | '
            'VAT 210,82 zł | Depozyt 402,01 zł | Do zapłaty 725,33 zł'
        ),
    },
]

# Suma kontrolna z blankietu zbiorczego
FORECAST_TOTAL_KWH = 5632.0
FORECAST_TOTAL_NETTO = 4808.84
FORECAST_TOTAL_BRUTTO = 5914.89


def main():
    importer = EnergyDataImporter()
    print('=' * 70)
    print('Import prognoz Tauron — blankiety 03/2025–02/2026')
    print('=' * 70)

    added = 0
    for row in TAURON_FORECASTS:
        try:
            importer.import_tauron_forecast(data_dict=row)
            print(f"  ✅ {row['forecast_period']} | {row['forecast_total_kwh']:.0f} kWh | "
                  f"brutto {row['forecast_total_cost']:.2f} zł")
            added += 1
        except Exception as e:
            logger.warning(f"  ⚠️  {row['forecast_period']}: {e}")

    sum_kwh = sum(r['forecast_total_kwh'] for r in TAURON_FORECASTS)
    sum_brutto = sum(r['forecast_total_cost'] for r in TAURON_FORECASTS)
    print('\n📊 Kontrola sum:')
    print(f'   kWh:    {sum_kwh:.0f} (blankiet: {FORECAST_TOTAL_KWH:.0f})')
    print(f'   brutto: {sum_brutto:.2f} zł (blankiet: {FORECAST_TOTAL_BRUTTO:.2f} zł)')

    summary = importer.get_data_summary()
    print(f"\n   Rekordów w tauron_forecast: {summary.get('tauron_forecast', 0)}")
    importer.close()
    print('\n💡 forecast_total_cost = kwota brutto z blankietu (baseline do ROI).')
    print('   „Do zapłaty” jest w polu notes (po odjęciu depozytu).')


if __name__ == '__main__':
    main()
