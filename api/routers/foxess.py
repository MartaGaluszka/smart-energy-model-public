"""FoxESS (TA.3): sync / overview / timeseries — thin wrappers, PII redacted."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from api.models import AppUser
from api.schemas.foxess import FoxOverviewResponse, FoxSyncRequest, FoxSyncResponse, FoxTimeseriesResponse
from api.services import foxess_sync

router = APIRouter(prefix='/api/v1/foxess', tags=['foxess'], dependencies=[Depends(get_current_user)])


@router.post('/sync', response_model=FoxSyncResponse, summary='Sync historii FoxESS w zadanym zakresie dat (upsert)')
def sync(body: FoxSyncRequest = FoxSyncRequest()) -> FoxSyncResponse:
    if body.start and body.end:
        return FoxSyncResponse(**foxess_sync.sync_range(body.start, body.end))
    return FoxSyncResponse(**foxess_sync.sync_incremental())


@router.get('/overview', response_model=FoxOverviewResponse, summary='KPI dnia: PV, SoC, import/export (§12.4)')
def overview(day: str | None = Query(default=None)) -> FoxOverviewResponse:
    return FoxOverviewResponse(**foxess_sync.get_overview(day))


@router.get('/timeseries', response_model=FoxTimeseriesResponse, summary='Punkty do wykresów dla danego dnia')
def timeseries(day: str | None = Query(default=None)) -> FoxTimeseriesResponse:
    return FoxTimeseriesResponse(**foxess_sync.get_timeseries(day))
