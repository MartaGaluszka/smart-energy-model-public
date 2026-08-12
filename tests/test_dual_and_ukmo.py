#!/usr/bin/env python
"""
Testy dual (16 + CS4) oraz kandydat UKMO — bez zmiany produkcji.

Uruchomienie:
    PYTHONPATH=$PWD python tests/test_dual_and_ukmo.py
    PYTHONPATH=$PWD python -m pytest tests/test_dual_and_ukmo.py -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')


def test_production_is_16_features() -> None:
    import joblib
    from src.features.pv_features_hourly_extended import HOURLY_FEATURE_COLUMNS_PRODUCTION

    path = ROOT / 'models' / 'pv_hourly_model.joblib'
    assert path.exists(), f'Brak {path}'
    bundle = joblib.load(path)
    cols = bundle['feature_columns']
    assert len(cols) == 16, f'Produkcja ma {len(cols)} cech, oczekiwano 16'
    assert list(cols) == list(HOURLY_FEATURE_COLUMNS_PRODUCTION)
    print(f'  ✓ produkcja: 16 cech ← {path.name}')


def test_cs4_candidate_model_exists() -> None:
    import joblib
    from src.features.pv_features_hourly_extended import HOURLY_FEATURE_COLUMNS_CS4

    path = ROOT / 'models' / 'pv_hourly_model_cs4.joblib'
    assert path.exists(), (
        f'Brak {path} — uruchom: ./scripts/analysis/run_cs4_sunday.sh'
    )
    bundle = joblib.load(path)
    cols = bundle['feature_columns']
    assert len(cols) == 19, f'CS4 ma {len(cols)} cech, oczekiwano 19'
    assert list(cols) == list(HOURLY_FEATURE_COLUMNS_CS4)
    for extra in ('cloud_cover_low_pct', 'cloud_cover_mid_pct', 'clearness'):
        assert extra in cols
    print(f'  ✓ CS4 kandydat: 19 cech ← {path.name}')


def test_ukmo_model_resolves() -> None:
    from src.data.weather_api import resolve_openmeteo_model

    assert resolve_openmeteo_model('ukmo_seamless') == 'ukmo_seamless'
    assert resolve_openmeteo_model('icon_seamless') == 'icon_seamless'
    # best_match → None (= domyślny serwera)
    assert resolve_openmeteo_model('best_match') is None
    print('  ✓ UKMO/ICON resolve_openmeteo_model OK')


def test_ukmo_client_sets_models_param() -> None:
    from src.data.weather_api import OpenMeteoClient

    client = OpenMeteoClient(50.06, 19.94, 'home', model='ukmo_seamless')
    params = client._with_model({'latitude': 50.06})
    assert params.get('models') == 'ukmo_seamless'
    print('  ✓ OpenMeteoClient(ukmo_seamless) ustawia models=ukmo_seamless')


def test_oneshot_ukmo_scripts_importable() -> None:
    """Skrypty UKMO muszą się importować (ścieżka testów podpięta)."""
    import importlib.util

    for rel in (
        'scripts/analysis/oneshot_icon_vs_ukmo_precip.py',
        'scripts/analysis/oneshot_rf_icon_vs_ukmo.py',
    ):
        path = ROOT / rel
        assert path.exists(), f'Brak {rel}'
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        # nie wykonuj main — tylko weryfikacja składni/ładowania modułu przez compile
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        print(f'  ✓ {rel} kompiluje się')


def test_cs4_shadow_script_exists() -> None:
    path = ROOT / 'mlops' / 'forecast_cs4_shadow.sh'
    assert path.exists()
    text = path.read_text(encoding='utf-8')
    assert 'FORECAST_CS4_SHADOW' in text
    assert 'daily_cs4' in text or 'RUN_LABEL' in text
    print('  ✓ mlops/forecast_cs4_shadow.sh obecny')


def main() -> None:
    print('=' * 60)
    print('TESTY: dual 16+CS4 · UKMO kandydat')
    print('=' * 60)
    tests = [
        test_production_is_16_features,
        test_cs4_candidate_model_exists,
        test_ukmo_model_resolves,
        test_ukmo_client_sets_models_param,
        test_oneshot_ukmo_scripts_importable,
        test_cs4_shadow_script_exists,
    ]
    for fn in tests:
        print()
        print(f'[{fn.__name__}]')
        fn()
    print()
    print('=' * 60)
    print('WSZYSTKIE TESTY OK')
    print('=' * 60)
    print('UKMO live oneshot: ./scripts/analysis/run_ukmo_tests.sh')


if __name__ == '__main__':
    main()
