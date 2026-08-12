"""
Smart Energy Model - Przykładowy skrypt do dodania danych Tauron

Ten plik pokazuje jak dodać:
1. Cennik Tauron G12w
2. Prognozy z rachunków Tauron
3. Rzeczywiste rachunki

Skopiuj ten plik, nazwij go np. 'add_my_tauron_data.py' 
i uzupełnij rzeczywistymi danymi z Twoich rachunków.
"""

import sys
sys.path.append('..')

from src.data.import_csv import EnergyDataImporter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    importer = EnergyDataImporter()
    
    print("=" * 70)
    print("Dodawanie danych Tauron do bazy")
    print("=" * 70)
    
    # =========================================================================
    # 1. CENNIK TAURON G12w
    # =========================================================================
    # Wypełnij rzeczywistymi danymi z Twojego rachunku!
    
    tauron_tariff = {
        'valid_from': '2026-06-01',  # Od kiedy obowiązuje ten cennik
        'tariff_name': 'G12w',
        
        # CENY ENERGII (z rachunku Tauron, sekcja "Energia elektryczna")
        'price_zone1_day': 0.85,      # Strefa dzienna (6-13, 15-22) [zł/kWh]
        'price_zone2_night': 0.45,    # Strefa nocna (22-6, 13-15) [zł/kWh]
        
        # DYSTRYBUCJA (z rachunku, sekcja "Usługi dystrybucji")
        'distribution_zone1': 0.25,   # Dystrybucja dzień [zł/kWh]
        'distribution_zone2': 0.15,   # Dystrybucja noc [zł/kWh]
        
        # OPŁATY STAŁE (z rachunku, sekcja "Opłaty stałe")
        'subscription_fee_monthly': 25.00,  # Abonament [zł/mc]
        'power_fee_monthly': 0.0,           # Opłata mocowa [zł/mc] (jeśli jest)
        
        # OPŁATY DODATKOWE
        'oze_fee_kwh': 0.02,              # Opłata OZE [zł/kWh]
        'cogenerative_fee_kwh': 0.0,      # Opłata kogeneracyjna [zł/kWh] (jeśli jest)
        
        'notes': 'Rzeczywiste stawki z rachunku Tauron - czerwiec 2026'
    }
    
    print("\n1️⃣  Dodawanie cennika Tauron...")
    try:
        importer.import_tauron_tariff(data_dict=tauron_tariff)
        print("✅ Cennik dodany pomyślnie!")
    except Exception as e:
        logger.warning(f"Cennik już istnieje lub błąd: {e}")
    
    # =========================================================================
    # 2. PROGNOZY TAURON (z rachunków zawierających prognozy)
    # =========================================================================
    
    # Przykład 1: Prognoza na styczeń 2026
    forecast_january = {
        'forecast_date': '2026-01-01',
        'forecast_period': '2026-01',  # Miesiąc lub okres
        
        # Z rachunku - sekcja "Prognozowane zużycie"
        'forecast_zone1_kwh': 450.0,    # Prognoza strefa dzienna [kWh]
        'forecast_zone2_kwh': 350.0,    # Prognoza strefa nocna [kWh]
        'forecast_total_kwh': 800.0,    # Całkowite prognozowane zużycie [kWh]
        
        # Z rachunku - "Prognozowany koszt"
        'forecast_total_cost': 720.0,   # Prognozowany koszt całkowity [zł]
        
        'source': 'rachunek_tauron',
        'notes': 'Prognoza z rachunku za styczeń 2026'
    }
    
    # Przykład 2: Prognoza na luty 2026
    forecast_february = {
        'forecast_date': '2026-02-01',
        'forecast_period': '2026-02',
        'forecast_zone1_kwh': 400.0,
        'forecast_zone2_kwh': 320.0,
        'forecast_total_kwh': 720.0,
        'forecast_total_cost': 650.0,
        'source': 'rachunek_tauron',
        'notes': 'Prognoza z rachunku za luty 2026'
    }
    
    print("\n2️⃣  Dodawanie prognoz Tauron...")
    forecasts = [forecast_january, forecast_february]
    
    for forecast in forecasts:
        try:
            importer.import_tauron_forecast(data_dict=forecast)
            print(f"   ✅ Dodano prognozę: {forecast['forecast_period']}")
        except Exception as e:
            logger.warning(f"   Prognoza już istnieje lub błąd: {e}")
    
    # =========================================================================
    # 3. RZECZYWISTE RACHUNKI (opcjonalnie - do zaawansowanej analizy)
    # =========================================================================
    # Możesz też dodać rzeczywiste rachunki do porównania
    
    print("\n" + "=" * 70)
    print("✅ Wszystkie dane Tauron dodane!")
    print("=" * 70)
    
    # Podsumowanie
    summary = importer.get_data_summary()
    print("\n📊 Aktualna zawartość bazy danych:")
    for table, count in summary.items():
        print(f"   {table:30s}: {count:>6d} rekordów")
    
    importer.close()
    
    print("\n💡 Następne kroki:")
    print("   1. Dodaj dane z FoxEss (CSV): python src/data/import_csv.py")
    print("   2. Uruchom analizę EDA: jupyter notebook notebooks/01_EDA_analiza_danych.ipynb")
    print("   3. Oblicz ROI: python src/financial/roi_calculator.py")


if __name__ == "__main__":
    main()
