"""
Smart Energy Model - Import danych do bazy danych

Ten skrypt importuje dane z różnych źródeł:
- Pliki CSV eksportowane z FoxEss Cloud
- FoxEss Cloud API (jeśli dostępne)
do bazy danych SQLite.
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Optional
from dotenv import load_dotenv

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnergyDataImporter:
    """Klasa do importu danych energetycznych do bazy danych"""
    
    def __init__(self, db_path='data/energy_model.db', use_api=False):
        """
        Inicjalizacja importera
        
        Args:
            db_path: Ścieżka do pliku bazy danych SQLite
            use_api: Czy używać API zamiast CSV (wymaga klucza API w .env)
        """
        self.db_path = db_path
        self.conn = None
        self.use_api = use_api
        self._ensure_database_exists()
        
        # Inicjalizacja API jeśli włączone
        if self.use_api:
            try:
                from .foxess_api import FoxEssAPI
                load_dotenv()
                self.api_client = FoxEssAPI()
                logger.info("✅ API Client zainicjalizowany")
            except Exception as e:
                logger.warning(f"⚠️ Nie udało się zainicjalizować API: {e}")
                logger.info("💡 Używam trybu CSV")
                self.use_api = False
                self.api_client = None
        else:
            self.api_client = None
    
    def _ensure_database_exists(self):
        """Tworzy bazę danych jeśli nie istnieje"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"Utworzono folder: {db_dir}")
        
        # Tworzenie bazy danych ze schematu
        if not os.path.exists(self.db_path):
            self._create_database()
    
    def _create_database(self):
        """Tworzy bazę danych ze schematu SQL"""
        schema_path = 'config/database_schema.sql'
        
        if not os.path.exists(schema_path):
            logger.error(f"Nie znaleziono schematu bazy danych: {schema_path}")
            return
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        
        logger.info(f"Utworzono bazę danych: {self.db_path}")
    
    def connect(self):
        """Nawiązuje połączenie z bazą danych"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        """Zamyka połączenie z bazą danych"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def import_foxess_from_api(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        device_sn: Optional[str] = None
    ) -> int:
        """
        Importuje dane bezpośrednio z FoxEss Cloud API
        
        Args:
            start_date: Data początkowa 'YYYY-MM-DD'
            end_date: Data końcowa 'YYYY-MM-DD' (opcjonalnie, domyślnie dzisiaj)
            device_sn: Numer seryjny urządzenia (opcjonalnie)
        
        Returns:
            int: Liczba zaimportowanych rekordów
        """
        if not self.use_api or not self.api_client:
            logger.error("❌ API nie jest włączone lub niedostępne")
            return 0
        
        logger.info(f"📡 Importuję dane z API: {start_date} - {end_date or 'dzisiaj'}")
        
        try:
            # Pobierz dane z API
            df = self.api_client.get_raw_data(start_date, end_date)
            
            if df.empty:
                logger.warning("⚠️ Brak danych z API")
                return 0
            
            # Dodaj metadane
            if device_sn:
                df['device_sn'] = device_sn
            df['data_source'] = 'api'
            
            # Przekształć nazwy kolumn (podobnie jak dla CSV)
            df = self._transform_foxess_dataframe(df, device_sn)
            
            # Import do bazy danych
            conn = self.connect()
            rows_inserted = df.to_sql(
                'foxess_data',
                conn,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            conn.commit()
            logger.info(f"✅ Zaimportowano {len(df)} rekordów z API")
            
            return len(df)
            
        except Exception as e:
            logger.error(f"❌ Błąd importu z API: {e}")
            return 0
    
    def import_foxess_csv(self, csv_path, device_sn=None):
        """
        Importuje dane z CSV eksportowanego z FoxEss Cloud
        
        Args:
            csv_path: Ścieżka do pliku CSV
            device_sn: Numer seryjny urządzenia (opcjonalny)
        
        Returns:
            int: Liczba zaimportowanych rekordów
        """
        logger.info(f"Importuję dane z: {csv_path}")
        
        try:
            # Wczytanie CSV
            df = pd.read_csv(csv_path)
            logger.info(f"Wczytano {len(df)} wierszy z CSV")
            
            # Przekształć DataFrame
            df = self._transform_foxess_dataframe(df, device_sn)
            
            # Import do bazy danych
            conn = self.connect()
            
            rows_inserted = df.to_sql(
                'foxess_data',
                conn,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            conn.commit()
            logger.info(f"✅ Zaimportowano {len(df)} rekordów do foxess_data")
            
            return len(df)
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas importu: {e}")
            raise
    
    def _transform_foxess_dataframe(self, df: pd.DataFrame, device_sn: Optional[str] = None) -> pd.DataFrame:
        """
        Przekształca DataFrame FoxEss do formatu bazy danych
        
        Args:
            df: DataFrame z danymi FoxEss
            device_sn: Numer seryjny urządzenia
        
        Returns:
            Przekształcony DataFrame
        """
        try:
            
            # Mapowanie kolumn - FoxEss Export
            # Mapowanie rzeczywistych nazw kolumn z FoxEss na nazwy w bazie danych
            column_mapping = {
                # Timestamp
                'timestamp': 'timestamp',
                'time': 'timestamp',
                'date': 'timestamp',
                'Time': 'timestamp',
                'Date': 'timestamp',
                
                # ========== PRODUKCJA PV ==========
                'GenerationPower (kW)': 'pv_power_kw',
                'Moc PV (kW)': 'pv_power_kw',
                'Moc PV1 (kW)': 'pv_power_kw',  # Jeśli masz tylko 1 string
                'generation_power': 'pv_power_kw',
                
                # ========== BATERIA ==========
                # Stan naładowania (SOC)
                'SoC (%)': 'battery_soc_percent',
                'soc': 'battery_soc_percent',
                'SOC': 'battery_soc_percent',
                
                # Moc baterii
                'invBatPower (kW)': 'battery_power_kw',
                'BatChargePower (kW)': 'battery_power_kw',  # Ładowanie (dodatnie)
                'BatDischargePower (kW)': 'battery_power_kw',  # Rozładowanie (ujemne)
                
                # Napięcie baterii
                'BatVolt (V)': 'battery_voltage_v',
                'InvBatVolt (V)': 'battery_voltage_v',
                
                # Temperatura baterii
                'batTemperature (℃)': 'battery_temp_celsius',
                
                # ========== ZUŻYCIE (LOADS) ==========
                'LoadsPower (kW)': 'load_power_kw',
                'loads_power': 'load_power_kw',
                
                # ========== SIEĆ (GRID) ==========
                # Import z sieci (pobór)
                'GridConsumptionPower (kW)': 'grid_import_kw',
                'grid_consumption': 'grid_import_kw',
                
                # Export do sieci (oddawanie)
                'FeedinPower (kW)': 'grid_export_kw',
                'feedin_power': 'grid_export_kw',
                
                # Moc licznika (może być + lub -)
                'MeterPower (kW)': 'grid_power_kw',
                'meter_power': 'grid_power_kw',
            }
            
            # Rename columns based on mapping
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)
            
            # Specjalna logika dla baterii FoxEss
            # FoxEss ma osobne kolumny dla charge i discharge
            # Konwertujemy na jedną kolumnę z odpowiednim znakiem
            if 'BatChargePower (kW)' in df.columns and 'BatDischargePower (kW)' in df.columns:
                # Ładowanie = dodatnie, Rozładowanie = ujemne
                df['battery_power_kw'] = df['BatChargePower (kW)'].fillna(0) - df['BatDischargePower (kW)'].fillna(0)
            
            # Konwersja mocy na energię (jeśli nie ma bezpośrednio energii)
            # Zakładamy próbkowanie co 5 minut = 1/12 godziny
            if 'pv_power_kw' in df.columns and 'pv_energy_kwh' not in df.columns:
                df['pv_energy_kwh'] = df['pv_power_kw'] * (5/60)  # 5 min = 5/60 h
            
            if 'load_power_kw' in df.columns and 'load_energy_kwh' not in df.columns:
                df['load_energy_kwh'] = df['load_power_kw'] * (5/60)
            
            if 'grid_import_kw' in df.columns and 'grid_import_kwh' not in df.columns:
                df['grid_import_kwh'] = df['grid_import_kw'] * (5/60)
            
            if 'grid_export_kw' in df.columns and 'grid_export_kwh' not in df.columns:
                df['grid_export_kwh'] = df['grid_export_kw'] * (5/60)
            
            # Parsowanie timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Dodanie device_sn jeśli podany
            if device_sn:
                df['device_sn'] = device_sn
            
            df['data_source'] = 'csv'
            
            # Filtrowanie tylko kolumn, które istnieją w tabeli
            valid_columns = [
                'timestamp', 'pv_power_kw', 'pv_energy_kwh', 'pv_energy_daily_kwh',
                'battery_soc_percent', 'battery_power_kw', 'battery_energy_kwh',
                'load_power_kw', 'load_energy_kwh', 'load_energy_daily_kwh',
                'grid_import_kwh', 'grid_export_kwh', 'grid_power_kw',
                'device_sn', 'data_source'
            ]
            
            # Wybierz tylko kolumny, które są w df i valid_columns
            columns_to_insert = [col for col in valid_columns if col in df.columns]
            return df[columns_to_insert]
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas przekształcania danych: {e}")
            raise
    
    def import_tauron_tariff(self, csv_path=None, data_dict=None):
        """
        Importuje cennik Tauron
        
        Args:
            csv_path: Ścieżka do pliku CSV z cennikiem (opcjonalny)
            data_dict: Słownik z danymi cennika (opcjonalny)
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        if data_dict:
            # UPSERT po valid_from (wymaga UNIQUE INDEX idx_tauron_tariff_valid_from —
            # config/database_schema.sql). Bez tego ponowne uruchomienie skryptu dla tego
            # samego miesiąca (np. poprawka literówki w stawce) dopisywało DRUGI wiersz z tą
            # samą datą "Ważne od" zamiast nadpisać pierwszy — który z dwóch wtedy "wygrywał"
            # przy rozliczeniu zależało od nieokreślonej kolejności SQL dla remisów.
            cursor.execute('''
                INSERT INTO tauron_tariff (
                    valid_from, tariff_name, price_zone1_day, price_zone2_night,
                    distribution_zone1, distribution_zone2, subscription_fee_monthly,
                    power_fee_monthly, transition_fee_monthly,
                    oze_fee_kwh, cogenerative_fee_kwh, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(valid_from) DO UPDATE SET
                    tariff_name = excluded.tariff_name,
                    price_zone1_day = excluded.price_zone1_day,
                    price_zone2_night = excluded.price_zone2_night,
                    distribution_zone1 = excluded.distribution_zone1,
                    distribution_zone2 = excluded.distribution_zone2,
                    subscription_fee_monthly = excluded.subscription_fee_monthly,
                    power_fee_monthly = excluded.power_fee_monthly,
                    transition_fee_monthly = excluded.transition_fee_monthly,
                    oze_fee_kwh = excluded.oze_fee_kwh,
                    cogenerative_fee_kwh = excluded.cogenerative_fee_kwh,
                    notes = excluded.notes
            ''', (
                data_dict.get('valid_from'),
                data_dict.get('tariff_name', 'G12w'),
                data_dict.get('price_zone1_day'),
                data_dict.get('price_zone2_night'),
                data_dict.get('distribution_zone1'),
                data_dict.get('distribution_zone2'),
                data_dict.get('subscription_fee_monthly'),
                data_dict.get('power_fee_monthly'),
                data_dict.get('transition_fee_monthly'),
                data_dict.get('oze_fee_kwh'),
                data_dict.get('cogenerative_fee_kwh'),
                data_dict.get('notes', '')
            ))
            conn.commit()
            logger.info("✅ Zaimportowano/zaktualizowano cennik Tauron (upsert po valid_from)")
        
        elif csv_path:
            # Import z CSV
            df = pd.read_csv(csv_path)
            df.to_sql('tauron_tariff', conn, if_exists='append', index=False)
            logger.info(f"✅ Zaimportowano {len(df)} rekordów do tauron_tariff")
    
    def import_tauron_forecast(self, csv_path=None, data_dict=None):
        """
        Importuje prognozy Tauron (z rachunków)
        
        Args:
            csv_path: Ścieżka do pliku CSV (opcjonalny)
            data_dict: Słownik z danymi prognozy (opcjonalny)
        """
        conn = self.connect()
        
        if data_dict:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tauron_forecast (
                    forecast_date, forecast_period,
                    forecast_zone1_kwh, forecast_zone2_kwh, forecast_total_kwh,
                    forecast_energy_cost, forecast_total_cost, source, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data_dict.get('forecast_date'),
                data_dict.get('forecast_period'),
                data_dict.get('forecast_zone1_kwh'),
                data_dict.get('forecast_zone2_kwh'),
                data_dict.get('forecast_total_kwh'),
                data_dict.get('forecast_energy_cost'),
                data_dict.get('forecast_total_cost'),
                data_dict.get('source', 'rachunek_tauron'),
                data_dict.get('notes', '')
            ))
            conn.commit()
            logger.info("✅ Zaimportowano prognozę Tauron")
        
        elif csv_path:
            df = pd.read_csv(csv_path)
            df.to_sql('tauron_forecast', conn, if_exists='append', index=False)
            logger.info(f"✅ Zaimportowano {len(df)} rekordów do tauron_forecast")

    def import_tauron_bill(self, data_dict: dict) -> None:
        """Importuje rzeczywisty rachunek / fakturę korygującą Tauron.

        UPSERT po (billing_period_start, billing_period_end) — zgodnie z zasadą: faktura
        korygująca dla okresu, który już ma zapisany rachunek (oryginał lub wcześniejsza
        korekta), NADPISUJE go w miejscu (nowy `bill_number`, nowe kwoty) zamiast dokładać
        drugi wiersz obok. Referencję do poprzedniej faktury warto zapisać w `notes`/`pdf_path`
        korekty (np. `do_faktury=...`) — sama tabela trzyma tylko AKTUALNIE obowiązujący wynik
        rozliczenia danego okresu, bez ręcznego `DELETE` przed importem.
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO tauron_bills (
                bill_date, billing_period_start, billing_period_end,
                actual_zone1_kwh, actual_zone2_kwh, actual_total_kwh,
                actual_energy_cost, actual_distribution_cost, actual_fixed_costs,
                actual_total_cost, energy_exported_kwh, energy_exported_value,
                bill_number, pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(billing_period_start, billing_period_end) DO UPDATE SET
                bill_date = excluded.bill_date,
                actual_zone1_kwh = excluded.actual_zone1_kwh,
                actual_zone2_kwh = excluded.actual_zone2_kwh,
                actual_total_kwh = excluded.actual_total_kwh,
                actual_energy_cost = excluded.actual_energy_cost,
                actual_distribution_cost = excluded.actual_distribution_cost,
                actual_fixed_costs = excluded.actual_fixed_costs,
                actual_total_cost = excluded.actual_total_cost,
                energy_exported_kwh = excluded.energy_exported_kwh,
                energy_exported_value = excluded.energy_exported_value,
                bill_number = excluded.bill_number,
                pdf_path = excluded.pdf_path
            ''',
            (
                data_dict.get('bill_date'),
                data_dict.get('billing_period_start'),
                data_dict.get('billing_period_end'),
                data_dict.get('actual_zone1_kwh'),
                data_dict.get('actual_zone2_kwh'),
                data_dict.get('actual_total_kwh'),
                data_dict.get('actual_energy_cost'),
                data_dict.get('actual_distribution_cost'),
                data_dict.get('actual_fixed_costs'),
                data_dict.get('actual_total_cost'),
                data_dict.get('energy_exported_kwh'),
                data_dict.get('energy_exported_value'),
                data_dict.get('bill_number'),
                data_dict.get('pdf_path'),
            ),
        )
        conn.commit()
        logger.info('✅ Zaimportowano/zaktualizowano rachunek Tauron (upsert po okresie rozliczeniowym)')
    
    def get_data_summary(self):
        """Zwraca podsumowanie danych w bazie"""
        conn = self.connect()
        cursor = conn.cursor()
        
        summary = {}
        
        tables = [
            'foxess_data',
            'tauron_tariff',
            'tauron_forecast',
            'tauron_bills',
            'weather_data'
        ]
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                summary[table] = count
            except sqlite3.OperationalError:
                summary[table] = 0
        
        return summary


def main():
    """Przykład użycia"""
    
    # Załaduj konfigurację
    load_dotenv()
    use_api = os.getenv('DATA_SOURCE', 'csv').lower() == 'api'
    
    # Inicjalizacja importera
    importer = EnergyDataImporter(use_api=use_api)
    
    print("=" * 70)
    print("Smart Energy Model - Import danych")
    print(f"Źródło danych: {'API' if use_api else 'CSV'}")
    print("=" * 70)
    
    # OPCJA 1: Pełne pobieranie z API (wszystkie zmienne)
    if use_api and importer.api_client:
        fetch_all = os.getenv('FOXESS_FETCH_ALL', '1').lower() in ('1', 'true', 'yes')
        if fetch_all:
            print("\n📡 Pobieram WSZYSTKIE dane z API (może potrwać kilka–kilkanaście min)...")
            print("   Ustaw FOXESS_FETCH_ALL=0 w .env aby tylko ostatnie 30 dni (szybciej).")
            try:
                stats = importer.api_client.fetch_all_data()
                print(f"✅ Zaimportowano {stats.get('timeseries_rows', 0)} punktów pomiarowych")
            except Exception as e:
                print(f"❌ Błąd: {e}")
        else:
            print("\n📡 Importuję dane z API (ostatnie 30 dni)...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            try:
                device_sn = os.getenv('FOXESS_DEVICE_SN') or None
                rows = importer.import_foxess_from_api(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    device_sn=device_sn,
                )
                print(f"✅ Zaimportowano {rows} rekordów z API")
            except Exception as e:
                print(f"❌ Błąd importu z API: {e}")
    
    # OPCJA 2: Import z CSV
    else:
        print("\n📁 Tryb CSV - zaimportuj dane ręcznie:")
        print("   1. Pobierz CSV z FoxEss Cloud")
        print("   2. Zapisz w data/raw/")
        print("   3. Odkomentuj poniższą linię i uruchom ponownie:")
        print()
        print("   # importer.import_foxess_csv('data/raw/foxess_2026.csv', device_sn='ABC123')")
        print()
    
    # Przykład: Dodanie cennika Tauron
    tauron_tariff = {
        'valid_from': '2026-01-01',
        'tariff_name': 'G12w',
        'price_zone1_day': 0.85,  # zł/kWh - strefa dzienna
        'price_zone2_night': 0.45,  # zł/kWh - strefa nocna
        'distribution_zone1': 0.25,
        'distribution_zone2': 0.15,
        'subscription_fee_monthly': 25.00,
        'oze_fee_kwh': 0.02,
        'notes': 'Rzeczywiste stawki z rachunku Tauron - czerwiec 2026'
    }
    
    try:
        # importer.import_tauron_tariff(data_dict=tauron_tariff)
        pass
    except sqlite3.IntegrityError:
        logger.info("Cennik już istnieje w bazie danych")
    
    # Podsumowanie danych
    print("\n📊 Podsumowanie danych w bazie:")
    print("-" * 70)
    summary = importer.get_data_summary()
    for table, count in summary.items():
        print(f"{table:30s}: {count:>6d} rekordów")
    print("=" * 70)
    
    # Zamknięcie połączenia
    importer.close()


if __name__ == "__main__":
    main()
