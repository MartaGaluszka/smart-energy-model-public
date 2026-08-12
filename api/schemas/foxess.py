from __future__ import annotations

from pydantic import BaseModel


class FoxSyncRequest(BaseModel):
    # Brak start/end -> backend sam dobiera brakujący zakres (patrz foxess_sync.sync_incremental).
    start: str | None = None
    end: str | None = None


class FoxSyncResponse(BaseModel):
    status: str
    start: str | None = None
    end: str | None = None
    days: int
    message: str


class FoxOverviewResponse(BaseModel):
    day: str
    pv_kwh: float | None = None
    soc_percent: float | None = None
    grid_import_kwh: float | None = None
    grid_export_kwh: float | None = None
    load_kwh: float | None = None
    device_sn_display: str = 'REDACTED'
    last_synced_at: str | None = None
    has_data: bool = True


class FoxTimeseriesPoint(BaseModel):
    timestamp: str
    pv_power_kw: float | None = None
    battery_soc_percent: float | None = None
    load_power_kw: float | None = None
    grid_power_kw: float | None = None


class FoxTimeseriesResponse(BaseModel):
    day: str
    points: list[FoxTimeseriesPoint]
