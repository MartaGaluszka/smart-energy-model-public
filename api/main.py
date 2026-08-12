"""FastAPI entrypoint (T0.7, T0.7b, T0.7c, T0.10, T0.10b).

Uruchomienie lokalne (dev, bez Dockera):
    source venv/bin/activate
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
    # OpenAPI: http://localhost:8000/docs

Uruchomienie w Docker Compose:
    docker compose up db api
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import get_settings
from api.db import init_db
from api.errors import ApiError
from api.middleware.request_id import RequestIDMiddleware
from api.routers import auth, battery, deposit, foxess, forecast, health, household, notifications, roi, simulate, tariff

logger = logging.getLogger('api')


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    init_db()

    # T0.10b: model .joblib ładowany RAZ, cache w app.state (nie na każde żądanie).
    try:
        from src.models.pv_hourly_predictor import PVHourlyPredictor

        predictor = PVHourlyPredictor(model_path=settings.PV_HOURLY_MODEL_PATH)
        predictor.load()
        app.state.pv_predictor = predictor
        logger.info('Model PV załadowany: %s', predictor.model_path)
    except FileNotFoundError as exc:
        app.state.pv_predictor = None
        logger.warning('Model PV niedostępny przy starcie (%s) — /forecast/hourly zwróci 503', exc)

    yield

    app.state.pv_predictor = None


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            'HTTP kontrakt dla aplikacji mobilnej Smart Energy (Ionic + Angular). '
            'Cienka warstwa nad istniejącym kodem src/* (ML PV, finanse, optymalizacja G12w). '
            'Patrz docs/PROJEKT_APLIKACJA_MOBILNA.md §12.'
        ),
        lifespan=lifespan,
        docs_url='/docs',
        redoc_url='/redoc',
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'detail': exc.detail,
                'code': exc.code,
                'request_id': getattr(request.state, 'request_id', None),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'detail': exc.detail,
                'code': 'HTTP_ERROR',
                'request_id': getattr(request.state, 'request_id', None),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                'detail': exc.errors(),
                'code': 'VALIDATION_ERROR',
                'request_id': getattr(request.state, 'request_id', None),
            },
        )

    # T0.7d: wszystkie endpointy biznesowe pod /api/v1 (health/ready są wyjątkiem — meta).
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(foxess.router)
    app.include_router(forecast.router)
    app.include_router(tariff.router)
    app.include_router(simulate.router)
    app.include_router(roi.router)
    app.include_router(battery.router)
    app.include_router(notifications.router)
    app.include_router(household.router)
    app.include_router(deposit.router)

    return app


app = create_app()
