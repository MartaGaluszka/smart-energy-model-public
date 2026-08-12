"""
Smart Energy Model - FoxEss Cloud API Integration
"""

import os
import pandas as pd
import foxesscloud.openapi as foxess
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
from dotenv import load_dotenv

foxess.debug_setting = 99

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FoxEssAPI:
    """Klient FoxEss Cloud Open API (wystarczy FOXESS_API_KEY)."""

    def __init__(self, api_key: Optional[str] = None, device_sn: Optional[str] = None):
        load_dotenv()

        raw_key = api_key or os.getenv('FOXESS_API_KEY') or os.getenv('FOXESS_TOKEN')
        self.api_key = (raw_key or '').strip().strip('"').strip("'")
        self.device_sn = device_sn or os.getenv('FOXESS_DEVICE_SN') or None
        if self.device_sn == '':
            self.device_sn = None

        if not self.api_key:
            raise ValueError(
                "Brak klucza API. Ustaw FOXESS_API_KEY w .env "
                "(User Profile → API Management)."
            )

        foxess.api_key = self.api_key
        if self.device_sn:
            foxess.device_sn = self.device_sn

        logger.info("✅ FoxEss API zainicjalizowane")

    def test_connection(self) -> bool:
        try:
            device = foxess.get_device()
            if device:
                sn = device.get('deviceSN') or device.get('sn')
                if sn and not self.device_sn:
                    self.device_sn = sn
                    foxess.device_sn = sn
                logger.info(f"✅ Połączenie OK — {sn}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Błąd: {e}")
            return False

    def get_device_info(self) -> Dict:
        try:
            return foxess.get_device() or {}
        except Exception as e:
            logger.error(f"❌ {e}")
            return {}

    def list_variables(self) -> List[str]:
        """Wszystkie zmienne dostępne dla urządzenia (real-time query)."""
        foxess.get_device()
        return foxess.get_vars() or []

    def fetch_all_data(
        self,
        days: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db_path: str = 'data/energy_model.db',
        save_csv: bool = True,
    ) -> dict:
        """Pobiera wszystkie zmienne + zapis do bazy i CSV."""
        from .foxess_fetch_all import fetch_all
        foxess.api_key = self.api_key
        if self.device_sn:
            foxess.device_sn = self.device_sn
        return fetch_all(
            days=days,
            start_date=start_date,
            end_date=end_date,
            db_path=db_path,
            save_csv=save_csv,
        )

    def get_raw_data(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        variables: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Pobiera historię dzień po dniu (wszystkie lub wybrane zmienne)."""
        from .foxess_fetch_all import history_result_to_long, history_to_wide

        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        foxess.get_device()
        if variables is None:
            variables = foxess.get_vars()
        if not variables:
            return pd.DataFrame()

        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        device_sn = foxess.device_sn

        chunks = []
        day = start
        while day <= end:
            d = day.strftime('%Y-%m-%d')
            result = foxess.get_history('day', d=d, v=variables, summary=0, plot=0)
            if result:
                chunks.append(history_result_to_long(result, device_sn))
            day += timedelta(days=1)

        if not chunks:
            return pd.DataFrame()

        long_df = pd.concat(chunks, ignore_index=True)
        return history_to_wide(long_df)

    def get_latest_snapshot(self) -> Dict:
        """Aktualne wartości wszystkich zmiennych."""
        foxess.get_device()
        data = foxess.get_real(version=1)
        if not data:
            return {}
        if isinstance(data, list) and len(data) > 0:
            datas = data[0].get('datas', data)
            return {x['variable']: x.get('value') for x in datas}
        return {}


def main():
    print("=" * 70)
    print("FoxEss Cloud API")
    print("=" * 70)
    try:
        api = FoxEssAPI()
        if api.test_connection():
            vars_list = api.list_variables()
            print(f"\n📋 Dostępne zmienne ({len(vars_list)}):")
            for v in vars_list[:20]:
                print(f"   • {v}")
            if len(vars_list) > 20:
                print(f"   ... i {len(vars_list) - 20} więcej")
            print("\n💡 Pełne pobieranie: python src/data/foxess_fetch_all.py")
    except ValueError as e:
        print(f"❌ {e}")


if __name__ == "__main__":
    main()
