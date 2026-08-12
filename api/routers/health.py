"""GET /health (liveness), GET /ready (readiness) — T0.7a. Bez auth, bez /api/v1 prefiksu."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from api.config import get_settings
from api.db import SessionLocal
from api.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=['meta'])


def _db_ping() -> bool:
    try:
        session = SessionLocal()
        try:
            session.execute(text('SELECT 1'))
            return True
        finally:
            session.close()
    except Exception:  # noqa: BLE001
        return False


@router.get('/health', response_model=HealthResponse, summary='Liveness — status + wersja API + ping DB')
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status='ok', version=settings.APP_VERSION, db_ok=_db_ping())


@router.get('/ready', response_model=ReadyResponse, summary='Readiness — DB + obecność modelu .joblib')
def ready(request: Request, response: Response) -> ReadyResponse:
    settings = get_settings()
    db_ok = _db_ping()
    model_ok = os.path.exists(settings.model_path_resolved) or getattr(request.app.state, 'pv_predictor', None) is not None

    if not (db_ok and model_ok):
        response.status_code = 503

    return ReadyResponse(
        status='ok' if (db_ok and model_ok) else 'not_ready',
        db_ok=db_ok,
        model_ok=model_ok,
        model_path=settings.model_path_resolved,
    )
