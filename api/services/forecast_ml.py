"""Adapter FastAPI -> src/models/pv_hourly_predictor.py, forecast_validation.py.

Model .joblib jest ładowany RAZ przy starcie (lifespan w main.py) i cache'owany
w `app.state.pv_predictor` (T0.10b) — ten moduł go używa, a nie ładuje ponownie.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from api.config import get_settings
from api.errors import ApiError


def get_hourly_forecast(predictor, day: str | None = None) -> dict:
    target_day = day or date.today().isoformat()

    try:
        from datetime import date as date_cls

        base_date = date_cls.fromisoformat(target_day)
        # hybrid_today=False (celowo, inaczej niż domyślne True) — ten endpoint zasila
        # WYŁĄCZNIE zakładkę "Prognoza" (wykres godzinowy + "Suma prognozy"), której celem
        # jest walidacja modelu NWP+RF ("prognoza vs rzeczywistość"). Domyślny tryb hybrydowy
        # podmienia predicted_kwh na rzeczywisty pomiar dla godzin, które już minęły — to
        # ukrywa błędy modelu (np. godz. 12:00 z realną awarią produkcji ~0,4 kWh nadpisywała
        # oryginalną prognozę ~3,9 kWh, więc na wykresie "błąd" po prostu znikał) i sprawiało,
        # że "Suma prognozy" zmieniała się w ciągu dnia niezależnie od zarchiwizowanych runów
        # 05:00/12:00/16:00. Z hybrid_today=False linia "Prognoza" to zawsze CZYSTY wynik
        # modelu (na bazie prognozy pogody, nie archiwum obserwacji) — "Rzeczywistość" nadal
        # pokazywana jest osobno (actual_by_hour niżej), więc obie linie mogą się różnić i
        # dopiero to pokazuje prawdziwą jakość prognozy. Inne konsumenty predict_days
        # (rekomendacje na Home, mlops/forecast_pv.py archiwizujący 05:00/12:00/16:00) mają
        # OSOBNE wywołania i nie są tym dotknięte.
        predictions = predictor.predict_days(days_ahead=1, from_date=base_date, hybrid_today=False)
    except (ValueError, KeyError) as exc:
        raise ApiError(422, 'FORECAST_NO_WEATHER_DATA', f'Brak danych pogodowych dla {target_day}: {exc}') from exc

    day_frame = predictions[predictions['day'] == target_day]
    if day_frame.empty:
        raise ApiError(422, 'FORECAST_NO_WEATHER_DATA', f'Brak prognozy dla dnia {target_day} (brak cech pogodowych)')

    from src.models.forecast_validation import get_actual_hourly_ml

    settings = get_settings()
    try:
        actual_df = get_actual_hourly_ml(target_day, db_path=settings.DATABASE_PATH)
        actual_by_hour = {
            int(r.hour): float(r.actual_pv_ml_kwh) for r in actual_df.itertuples(index=False)
        }
    except Exception:
        actual_by_hour = {}

    hours = []
    for row in day_frame.itertuples(index=False):
        hour = int(row.hour)
        predicted = float(row.predicted_kwh)
        actual = actual_by_hour.get(hour)
        # Zerowa produkcja nocą jest poprawnym pomiarem (nie "brak danych") — pokazuj ją,
        # ale nie licz błędu % względem 0 (dzielenie przez zero / bez sensu procentowo).
        error_pct = round((predicted - actual) / actual * 100, 1) if actual not in (None, 0) else None
        hours.append({
            'hour': hour,
            'predicted_kwh': round(predicted, 3),
            'prediction_source': str(row.prediction_source),
            'actual_kwh': round(actual, 3) if actual is not None else None,
            'error_pct': error_pct,
        })
    total_kwh = round(float(day_frame['predicted_kwh'].sum()), 2)

    return {
        'day': target_day,
        'hours': hours,
        'total_kwh': total_kwh,
        'model_path': predictor.model_path,
    }


def get_forecast_validation(day: str) -> dict:
    from src.models.forecast_validation import (
        build_daily_forecast_summary,
        build_hourly_peak_validation,
        get_actual_pv_ml,
        target_day_is_complete,
    )

    settings = get_settings()
    hourly_df, peaks_df = build_hourly_peak_validation(day, db_path=settings.DATABASE_PATH)
    daily_df = build_daily_forecast_summary(day, db_path=settings.DATABASE_PATH)

    is_complete = target_day_is_complete(day)
    actual_so_far_kwh = None
    if not is_complete:
        so_far = get_actual_pv_ml(day, db_path=settings.DATABASE_PATH)
        if so_far is not None and so_far > 0:
            actual_so_far_kwh = round(so_far, 2)

    note = None
    if hourly_df.empty and peaks_df.empty and daily_df.empty:
        note = 'Brak zarchiwizowanej prognozy (forecast_history) dla tego dnia — pusta walidacja.'

    def _nan_to_none(records: list[dict]) -> list[dict]:
        # NaN nie jest poprawnym JSON-em (Starlette JSONResponse: allow_nan=False) —
        # pandas .where(...) na kolumnach float64 z powrotem konwertuje None -> NaN,
        # więc czyścimy ręcznie po zrzucie do dict.
        cleaned = []
        for row in records:
            cleaned.append({k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in row.items()})
        return cleaned

    def _hourly_rows() -> list[dict]:
        if hourly_df.empty:
            return []
        cols = [
            'run_label', 'rank', 'predicted_hour', 'predicted_kwh',
            'actual_pv_ml_kwh', 'actual_report_kwh', 'error_vs_ml_kwh', 'error_vs_ml_pct',
        ]
        return _nan_to_none(hourly_df[cols].to_dict(orient='records'))

    def _peak_rows() -> list[dict]:
        if peaks_df.empty:
            return []
        cols = ['run_label', 'predicted_peak_hour', 'predicted_peak_kwh', 'actual_peak_hour_ml', 'actual_peak_kwh_ml']
        return _nan_to_none(peaks_df[cols].to_dict(orient='records'))

    def _daily_rows() -> list[dict]:
        if daily_df.empty:
            return []
        cols = [
            'run_label', 'forecast_run_at', 'predicted_total_kwh', 'outlook_mode',
            'actual_total_kwh', 'error_kwh', 'error_pct',
        ]
        # outlook_mode może brakować w starszych DF
        cols = [c for c in cols if c in daily_df.columns]
        return _nan_to_none(daily_df[cols].to_dict(orient='records'))

    return {
        'day': day,
        'daily': _daily_rows(),
        'hourly': _hourly_rows(),
        'peaks': _peak_rows(),
        'note': note,
        'is_complete': is_complete,
        'actual_so_far_kwh': actual_so_far_kwh,
    }
