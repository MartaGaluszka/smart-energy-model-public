"""
Smart Energy Model - Moduł finansowy (ROI)

Moduł do obliczania zwrotu z inwestycji i oszczędności
przez porównanie prognoz operatora (Tauron) z rzeczywistymi kosztami.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinancialAnalyzer:
    """Klasa do analizy finansowej i obliczania ROI"""
    
    def __init__(self, db_path='data/energy_model.db'):
        """
        Inicjalizacja analizatora finansowego
        
        Args:
            db_path: Ścieżka do bazy danych
        """
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Nawiązuje połączenie z bazą danych"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        """Zamyka połączenie"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def get_tariff_prices(self, date: str = None) -> Dict[str, float]:
        """
        Pobiera aktualne stawki taryfowe dla danej daty
        
        Args:
            date: Data w formacie 'YYYY-MM-DD' (domyślnie: dzisiaj)
        
        Returns:
            Słownik ze stawkami
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = self.connect()
        query = """
            SELECT * FROM tauron_tariff
            WHERE valid_from <= ?
            AND (valid_to IS NULL OR valid_to >= ?)
            ORDER BY valid_from DESC
            LIMIT 1
        """
        
        df = pd.read_sql_query(query, conn, params=(date, date))
        
        if len(df) == 0:
            logger.warning("Nie znaleziono cennika dla podanej daty")
            return {}
        
        return df.iloc[0].to_dict()
    
    def calculate_energy_cost(self, 
                            zone1_kwh: float, 
                            zone2_kwh: float,
                            date: str = None) -> Dict[str, float]:
        """
        Oblicza koszt energii dla danego zużycia
        
        Args:
            zone1_kwh: Zużycie w strefie dziennej [kWh]
            zone2_kwh: Zużycie w strefie nocnej [kWh]
            date: Data dla wybrania odpowiedniego cennika
        
        Returns:
            Słownik z rozbiciem kosztów
        """
        tariff = self.get_tariff_prices(date)
        
        if not tariff:
            logger.error("Brak cennika w bazie danych")
            return {}
        
        # Koszt energii
        energy_cost_zone1 = zone1_kwh * (tariff['price_zone1_day'] + tariff.get('distribution_zone1', 0))
        energy_cost_zone2 = zone2_kwh * (tariff['price_zone2_night'] + tariff.get('distribution_zone2', 0))
        
        # Opłaty dodatkowe proporcjonalne do zużycia
        total_kwh = zone1_kwh + zone2_kwh
        oze_cost = total_kwh * tariff.get('oze_fee_kwh', 0)
        
        total_energy_cost = energy_cost_zone1 + energy_cost_zone2 + oze_cost
        
        return {
            'energy_cost_zone1': round(energy_cost_zone1, 2),
            'energy_cost_zone2': round(energy_cost_zone2, 2),
            'oze_cost': round(oze_cost, 2),
            'total_energy_cost': round(total_energy_cost, 2),
            'subscription_fee': tariff.get('subscription_fee_monthly', 0),
            'total_cost': round(total_energy_cost + tariff.get('subscription_fee_monthly', 0), 2)
        }
    
    def calculate_baseline_cost(self, 
                               start_date: str, 
                               end_date: str,
                               use_forecast: bool = True) -> float:
        """
        Oblicza koszt baseline (bez optymalizacji)
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
            use_forecast: Czy użyć prognozy Tauron (True) czy rzeczywistego zużycia (False)
        
        Returns:
            Całkowity koszt baseline [zł]
        """
        conn = self.connect()
        
        if use_forecast:
            # Użyj prognoz Tauron
            query = """
                SELECT 
                    SUM(forecast_total_cost) as total_cost
                FROM tauron_forecast
                WHERE forecast_date BETWEEN ? AND ?
            """
            df = pd.read_sql_query(query, conn, params=(start_date, end_date))
            
            if df['total_cost'].isna().all():
                logger.warning("Brak prognoz Tauron - używam standardowego obliczenia")
                return self._calculate_baseline_from_load(start_date, end_date)
            
            return float(df['total_cost'].iloc[0])
        else:
            # Oblicz na podstawie rzeczywistego zużycia
            return self._calculate_baseline_from_load(start_date, end_date)
    
    def _calculate_baseline_from_load(self, start_date: str, end_date: str) -> float:
        """
        Oblicza koszt baseline na podstawie rzeczywistego zużycia
        zakładając brak optymalizacji (standardowy profil G12w)
        """
        conn = self.connect()
        
        # Pobierz rzeczywiste zużycie
        query = """
            SELECT 
                timestamp,
                load_energy_kwh
            FROM foxess_data
            WHERE DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        # foxess_data miesza wiersze z offsetem ("+02:00") i bez (naive) — oba to ten sam
        # lokalny czas zegarowy. format='mixed' samo nie wystarcza, gdy w wyniku są OBA typy
        # naraz (pandas: "Mixed timezones detected"), więc najpierw ucinamy sufiks offsetu.
        df['timestamp'] = pd.to_datetime(
            df['timestamp'].astype(str).str.replace(r'[+-]\d{2}:\d{2}$', '', regex=True), format='mixed'
        )
        from src.optimization.g12w_tariff import classify_zone as g12w_zone

        df['zone'] = df['timestamp'].apply(g12w_zone)
        
        # Suma zużycia w strefach
        zone1_kwh = df[df['zone'] == 1]['load_energy_kwh'].sum()
        zone2_kwh = df[df['zone'] == 2]['load_energy_kwh'].sum()
        
        # Oblicz koszt
        costs = self.calculate_energy_cost(zone1_kwh, zone2_kwh, start_date)
        
        return costs['total_cost']
    
    def calculate_actual_cost(self, start_date: str, end_date: str) -> float:
        """
        Oblicza rzeczywisty koszt z uwzględnieniem optymalizacji
        (bateria, autoconsumption, itd.)
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
        
        Returns:
            Rzeczywisty koszt [zł]
        """
        conn = self.connect()
        
        # Pobierz dane o wymianie energii z siecią
        query = """
            SELECT 
                timestamp,
                grid_import_kwh,
                grid_export_kwh
            FROM foxess_data
            WHERE DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        df['timestamp'] = pd.to_datetime(
            df['timestamp'].astype(str).str.replace(r'[+-]\d{2}:\d{2}$', '', regex=True), format='mixed'
        )
        df['hour'] = df['timestamp'].dt.hour
        
        # Klasyfikacja stref
        def classify_zone(hour):
            if (6 <= hour < 13) or (15 <= hour < 22):
                return 1
            else:
                return 2
        
        df['zone'] = df['hour'].apply(classify_zone)
        
        # Import z sieci (to za co realnie płacimy — §7.3: "z PV ≈ import z sieci × stawki").
        # UWAGA: NIE odejmujemy eksportu w tej samej strefie ("netto"), bo to daje fałszywy
        # wynik gdy eksport regularnie przewyższa import (typowe latem przy PV) — koszt
        # spadałby do 0 niezależnie od realnego zużycia. Eksport rozlicza się osobno
        # (depozyt prosumencki wg RCEm — jeszcze nie wliczony, zob. T2.8), a nie 1:1 tutaj.
        zone1_import = df[df['zone'] == 1]['grid_import_kwh'].sum()
        zone2_import = df[df['zone'] == 2]['grid_import_kwh'].sum()

        # Oblicz koszt
        costs = self.calculate_energy_cost(zone1_import, zone2_import, start_date)
        
        return costs['total_cost']
    
    def calculate_roi(self, 
                     start_date: str, 
                     end_date: str,
                     use_forecast_baseline: bool = True) -> Dict[str, float]:
        """
        Oblicza ROI przez porównanie baseline vs rzeczywisty koszt
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
            use_forecast_baseline: Czy użyć prognozy Tauron jako baseline
        
        Returns:
            Słownik z metrykami ROI
        """
        logger.info(f"Obliczanie ROI dla okresu: {start_date} - {end_date}")
        
        # Koszt baseline (bez optymalizacji)
        baseline_cost = self.calculate_baseline_cost(start_date, end_date, use_forecast_baseline)
        
        # Rzeczywisty koszt (z optymalizacją)
        actual_cost = self.calculate_actual_cost(start_date, end_date)
        
        # Oszczędności
        savings = baseline_cost - actual_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0
        
        # Dodatkowe metryki
        conn = self.connect()
        query = """
            SELECT 
                SUM(pv_energy_kwh) as total_pv,
                SUM(load_energy_kwh) as total_load,
                SUM(grid_import_kwh) as total_import,
                SUM(grid_export_kwh) as total_export
            FROM foxess_data
            WHERE DATE(timestamp) BETWEEN ? AND ?
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        metrics = df.iloc[0].to_dict()
        
        # Współczynnik autokonsumpcji
        if metrics['total_pv'] > 0:
            self_consumption = (metrics['total_pv'] - metrics['total_export']) / metrics['total_pv'] * 100
        else:
            self_consumption = 0
        
        # Współczynnik samowystarczalności
        if metrics['total_load'] > 0:
            self_sufficiency = (metrics['total_load'] - metrics['total_import']) / metrics['total_load'] * 100
        else:
            self_sufficiency = 0
        
        roi_data = {
            'period_start': start_date,
            'period_end': end_date,
            'baseline_cost_pln': round(baseline_cost, 2),
            'actual_cost_pln': round(actual_cost, 2),
            'savings_pln': round(savings, 2),
            'savings_percent': round(savings_percent, 2),
            'total_pv_kwh': round(metrics['total_pv'], 2),
            'total_load_kwh': round(metrics['total_load'], 2),
            'total_import_kwh': round(metrics['total_import'], 2),
            'total_export_kwh': round(metrics['total_export'], 2),
            'self_consumption_rate': round(self_consumption, 2),
            'self_sufficiency_rate': round(self_sufficiency, 2)
        }
        
        return roi_data
    
    def save_roi_analysis(self, roi_data: Dict) -> None:
        """
        Zapisuje analizę ROI do bazy danych
        
        Args:
            roi_data: Słownik z danymi ROI
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO roi_analysis (
                analysis_date, period_start, period_end,
                baseline_cost_pln, actual_cost_pln,
                savings_pln, savings_percent,
                self_consumption_rate, self_sufficiency_rate,
                energy_exported_kwh, energy_imported_kwh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime('%Y-%m-%d'),
            roi_data['period_start'],
            roi_data['period_end'],
            roi_data['baseline_cost_pln'],
            roi_data['actual_cost_pln'],
            roi_data['savings_pln'],
            roi_data['savings_percent'],
            roi_data['self_consumption_rate'],
            roi_data['self_sufficiency_rate'],
            roi_data['total_export_kwh'],
            roi_data['total_import_kwh']
        ))
        
        conn.commit()
        logger.info("✅ Analiza ROI zapisana do bazy danych")
    
    def print_roi_report(self, roi_data: Dict) -> None:
        """Wyświetla raport ROI w czytelnej formie"""
        print("\n" + "=" * 70)
        print("📊 RAPORT ROI - Zwrot z Inwestycji".center(70))
        print("=" * 70)
        print(f"\n📅 Okres analizy: {roi_data['period_start']} - {roi_data['period_end']}")
        print("\n" + "-" * 70)
        print("💰 KOSZTY:")
        print("-" * 70)
        print(f"   Koszt baseline (prognoza/bez optymalizacji): {roi_data['baseline_cost_pln']:>10.2f} zł")
        print(f"   Koszt rzeczywisty (z optymalizacją):         {roi_data['actual_cost_pln']:>10.2f} zł")
        print(f"\n   {'='*20}")
        print(f"   💵 OSZCZĘDNOŚCI:                              {roi_data['savings_pln']:>10.2f} zł")
        print(f"   📈 Oszczędności [%]:                          {roi_data['savings_percent']:>10.2f} %")
        
        print("\n" + "-" * 70)
        print("⚡ ENERGIA:")
        print("-" * 70)
        print(f"   Produkcja PV:                                 {roi_data['total_pv_kwh']:>10.2f} kWh")
        print(f"   Zużycie całkowite:                            {roi_data['total_load_kwh']:>10.2f} kWh")
        print(f"   Import z sieci:                               {roi_data['total_import_kwh']:>10.2f} kWh")
        print(f"   Export do sieci:                              {roi_data['total_export_kwh']:>10.2f} kWh")
        
        print("\n" + "-" * 70)
        print("📈 WSKAŹNIKI:")
        print("-" * 70)
        print(f"   Współczynnik autokonsumpcji:                  {roi_data['self_consumption_rate']:>10.2f} %")
        print(f"   Współczynnik samowystarczalności:             {roi_data['self_sufficiency_rate']:>10.2f} %")
        
        print("\n" + "=" * 70)
        
        # Podsumowanie
        if roi_data['savings_pln'] > 0:
            print(f"✅ System zoptymalizowany przynosi oszczędności!")
            print(f"   Zaoszczędzono {roi_data['savings_pln']:.2f} zł ({roi_data['savings_percent']:.1f}%)")
        else:
            print(f"⚠️  System nie przynosi oszczędności w tym okresie")
        
        print("=" * 70 + "\n")


def main():
    """Przykład użycia"""
    from src.data.household_context import roi_date_range

    analyzer = FinancialAnalyzer()

    # ROI od normalnego użytkowania (01.09.2025) — patrz household_context.py
    start_date, end_date = roi_date_range()
    
    try:
        roi = analyzer.calculate_roi(start_date, end_date, use_forecast_baseline=True)
        analyzer.print_roi_report(roi)
        analyzer.save_roi_analysis(roi)
    except Exception as e:
        logger.error(f"Błąd podczas obliczania ROI: {e}")
        print("\n⚠️  Aby obliczyć ROI, potrzebne są dane w bazie danych:")
        print("   1. Dane z FoxEss (foxess_data)")
        print("   2. Cennik Tauron (tauron_tariff)")
        print("   3. Opcjonalnie: Prognozy Tauron (tauron_forecast)")
        print("\n💡 Użyj skryptu src/data/import_csv.py do importu danych")
    
    analyzer.close()


if __name__ == "__main__":
    main()
