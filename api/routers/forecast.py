"""Prognoza ML (TA.4): hourly + validation — inference z modelu załadowanego w app.state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.deps import get_current_user
from api.errors import ApiError
from api.schemas.forecast import ForecastValidationResponse, HourlyForecastResponse
from api.services import forecast_ml

router = APIRouter(prefix='/api/v1/forecast', tags=['forecast'], dependencies=[Depends(get_current_user)])


@router.get('/hourly', response_model=HourlyForecastResponse, summary='Szereg godzinowy kWh + suma dnia (joblib)')
def hourly(request: Request, day: str | None = Query(default=None)) -> HourlyForecastResponse:
    predictor = getattr(request.app.state, 'pv_predictor', None)
    if predictor is None:
        raise ApiError(503, 'MODEL_NOT_LOADED', 'Model PV nie jest załadowany (sprawdź /ready)')
    return HourlyForecastResponse(**forecast_ml.get_hourly_forecast(predictor, day))


@router.get('/validation', response_model=ForecastValidationResponse, summary='Prognoza vs actual / closeout')
def validation(day: str = Query(...)) -> ForecastValidationResponse:
    return ForecastValidationResponse(**forecast_ml.get_forecast_validation(day))
