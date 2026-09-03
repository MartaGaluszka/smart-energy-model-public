from __future__ import annotations

from pydantic import BaseModel


class HourlyForecastPoint(BaseModel):
    hour: int
    predicted_kwh: float
    prediction_source: str
    # Rzeczywista produkcja (Δ PVEnergyTotal) dla godzin, które już minęły — None dla przyszłości.
    actual_kwh: float | None = None
    # Błąd % = (predicted - actual) / actual * 100; dodatni = model przeszacował. None gdy brak actual.
    error_pct: float | None = None


class ApplianceTip(BaseModel):
    """Top godzina PV → kombinacja AGD w budżecie mocy (T1.20)."""

    hour: int
    predicted_kwh: float
    rank: int
    appliances: list[str]
    # Suma mocy wybranej kombinacji [kW]; 0 gdy za mało PV.
    load_kw: float = 0.0


class ApplianceThreshold(BaseModel):
    """Próg mocy [kW ≈ kWh/h] dla etykiety AGD."""

    key: str
    label: str
    min_kw: float


class HourlyForecastResponse(BaseModel):
    day: str
    hours: list[HourlyForecastPoint]
    total_kwh: float
    model_path: str
    appliance_tips: list[ApplianceTip] = []
    appliance_thresholds: list[ApplianceThreshold] = []


class ForecastValidationHourlyRow(BaseModel):
    run_label: str
    rank: int
    predicted_hour: int
    predicted_kwh: float
    actual_pv_ml_kwh: float | None = None
    actual_report_kwh: float | None = None
    error_vs_ml_kwh: float | None = None
    # Błąd % = (predicted - actual) / actual * 100; dodatni = model przeszacował.
    error_vs_ml_pct: float | None = None


class ForecastValidationPeakRow(BaseModel):
    run_label: str
    predicted_peak_hour: int
    predicted_peak_kwh: float
    actual_peak_hour_ml: int | None = None
    actual_peak_kwh_ml: float | None = None


class ForecastValidationDailyRow(BaseModel):
    run_label: str
    forecast_run_at: str | None = None
    predicted_total_kwh: float
    # model_raw | hybrid_path | adjusted — skąd wzięta suma dnia (outlook hybrydy)
    outlook_mode: str | None = None
    # Wypełnione DOPIERO gdy dzień jest zamknięty (patrz `ForecastValidationResponse.is_complete`)
    # — przeszły dzień, lub dziś po zachodzie słońca + margines (wieczorna synchronizacja, T1.17).
    # Dopóki dzień trwa: None (żadnego mylącego "błędu" liczonego względem produkcji, która
    # jeszcze narasta) — patrz `actual_so_far_kwh` niżej na poziomie całej odpowiedzi.
    actual_total_kwh: float | None = None
    error_kwh: float | None = None
    error_pct: float | None = None


class ForecastValidationResponse(BaseModel):
    day: str
    daily: list[ForecastValidationDailyRow]
    hourly: list[ForecastValidationHourlyRow]
    peaks: list[ForecastValidationPeakRow]
    note: str | None = None
    # True = dzień zamknięty (przeszły LUB dziś po zachodzie słońca + margines) — wartości
    # actual_total_kwh/error_* w `daily` są już ostateczne. False = dzień jeszcze trwa.
    is_complete: bool = True
    # Produkcja dnia z FoxESS (Δ PVEnergyTotal), niezależna od run_label — jak „Dzienna
    # produkcja” w apce. Dla dnia w toku = dotychczas; po zamknięciu / dni przeszłe =
    # ostateczna suma (tożsama z `daily[].actual_total_kwh`).
    actual_so_far_kwh: float | None = None
