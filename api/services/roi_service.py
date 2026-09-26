"""ROI: kumulacyjny zwrot z przepływów rachunku + depozytu RCEm (§8)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from api.config import get_settings
from api.errors import ApiError


def _month_slices(period_start: date, period_end: date) -> list[tuple[str, str, str]]:
    """Odcinki kalendarzowe miesiąc po miesiącu w [start, end]."""
    slices: list[tuple[str, str, str]] = []
    cur = period_start
    while cur <= period_end:
        last_day = monthrange(cur.year, cur.month)[1]
        month_end = date(cur.year, cur.month, last_day)
        seg_end = min(month_end, period_end)
        slices.append((cur.isoformat(), seg_end.isoformat(), f'{cur.year:04d}-{cur.month:02d}'))
        cur = seg_end + timedelta(days=1)
    return slices


def _deposit_for_slice(db_path: str, month: str, seg_start: str, seg_end: str) -> float:
    """RCEm za miesiąc, proporcjonalnie do dni odcinka (Tauron rozlicza miesięcznie)."""
    from src.financial.prosumer_deposit import calculate_prosumer_deposit_rcem

    try:
        summary = calculate_prosumer_deposit_rcem(db_path, month)
    except ValueError:
        return 0.0

    d0 = date.fromisoformat(seg_start)
    d1 = date.fromisoformat(seg_end)
    days_in_slice = (d1 - d0).days + 1
    days_in_month = monthrange(d0.year, d0.month)[1]
    if days_in_slice >= days_in_month:
        return float(summary.net_deposit_accrual_pln)
    return float(summary.net_deposit_accrual_pln) * (days_in_slice / days_in_month)


def calculate_roi(period_start: str, period_end: str, assumptions: dict, db, user_id: int) -> dict:
    """Zwrot z kumulacji: każdy miesiąc = oszczędność rachunku + depozyt RCEm − przegląd.

    Bez sztucznego „rozciągania” całego okna na 365 dni. Gdy w wybranym okresie
    CAPEX jeszcze nie wrócił, szacunek dokłada miesiące w tempie średniego zysku
    z zaobserwowanych miesięcy.
    """
    from api.services.bill_simulator import simulate_bill

    d0 = date.fromisoformat(period_start)
    d1 = date.fromisoformat(period_end)
    if d1 < d0:
        raise ApiError(422, 'ROI_INVALID_PERIOD', 'period_end musi być ≥ period_start')

    capex = float(assumptions.get('capex_pln', 0.0) or 0.0) + float(
        assumptions.get('battery_capex_pln') or 0.0
    )
    opex_year = float(assumptions.get('opex_pln_year', 0.0) or 0.0)
    settings = get_settings()

    bill_savings_total = 0.0
    deposit_total = 0.0
    opex_total = 0.0
    cumulative = 0.0
    series: list[dict] = []
    payback_date: date | None = None
    month_index = 0

    try:
        for seg_start, seg_end, month in _month_slices(d0, d1):
            month_index += 1
            bill = simulate_bill(seg_start, seg_end, db=db, user_id=user_id)
            bill_sav = float(bill['savings_gross_pln'])
            deposit = _deposit_for_slice(settings.DATABASE_PATH, month, seg_start, seg_end)
            seg_days = (date.fromisoformat(seg_end) - date.fromisoformat(seg_start)).days + 1
            opex = opex_year * (seg_days / 365.0)
            net = bill_sav + deposit - opex

            bill_savings_total += bill_sav
            deposit_total += deposit
            opex_total += opex
            prev = cumulative
            cumulative += net

            series.append(
                {
                    'year': month_index,  # tu: kolejny miesiąc obserwacji (kontrakt T3.4)
                    'cumulative_savings_pln': round(cumulative, 2),
                }
            )

            if payback_date is None and capex > 0 and prev < capex <= cumulative:
                # Interpolacja w obrębie miesiąca
                need = capex - prev
                frac = need / net if net > 0 else 1.0
                payback_date = date.fromisoformat(seg_start) + timedelta(
                    days=max(0, min(seg_days - 1, int(round(frac * seg_days) - 1)))
                )
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ApiError(422, 'ROI_CALCULATE_FAILED', f'Nie można policzyć ROI: {exc}') from exc

    period_days = max(1, (d1 - d0).days + 1)
    cash_gain_period = bill_savings_total + deposit_total - opex_total
    recovered = min(max(0.0, cumulative), capex) if capex > 0 else max(0.0, cumulative)
    remaining = max(0.0, capex - recovered) if capex > 0 else 0.0

    # Średni zysk „na rok” tylko jako informacja (tempo z wybranego okresu)
    avg_per_day = cash_gain_period / period_days
    savings_annualized = round(avg_per_day * 365.0, 2)

    payback_years: float | None = None
    remaining_years: float | None = None
    if capex > 0 and avg_per_day > 0:
        if payback_date is not None:
            payback_years = round((payback_date - d0).days / 365.25, 2)
            remaining_years = 0.0
        else:
            # Tempo z obserwacji → ile lat od startu do pełnego zwrotu
            total_days = capex / avg_per_day
            payback_years = round(total_days / 365.25, 2)
            remaining_years = round(remaining / avg_per_day / 365.25, 2)
    elif remaining <= 0 and capex > 0:
        remaining_years = 0.0

    roi_percent = None
    if capex > 0 and savings_annualized > 0:
        roi_percent = round(savings_annualized / capex * 100, 2)

    # Projekcja serii poza okresem, gdy zwrot jeszcze nie nastąpił (dla wykresu T3.4)
    if capex > 0 and remaining > 0 and avg_per_day > 0 and month_index > 0:
        inflation = 1 + (float(assumptions.get('inflation_pct', 0.0) or 0.0) / 100.0)
        monthly_avg = cash_gain_period / month_index
        proj = cumulative
        year_like = month_index
        while proj < capex * 1.05 and year_like < month_index + 240:
            year_like += 1
            monthly_avg *= inflation ** (1 / 12)
            proj += monthly_avg
            series.append({'year': year_like, 'cumulative_savings_pln': round(proj, 2)})
            if proj >= capex:
                break

    return {
        'period_start': period_start,
        'period_end': period_end,
        'savings_pln_period': round(bill_savings_total, 2),
        'deposit_pln_period': round(deposit_total, 2),
        'opex_pln_period': round(opex_total, 2),
        'cash_gain_pln_period': round(cash_gain_period, 2),
        'recovered_pln': round(recovered, 2),
        'remaining_pln': round(remaining, 2),
        'remaining_years': remaining_years,
        'savings_pln_year_annualized': savings_annualized,
        'roi_percent': roi_percent,
        'payback_years': payback_years,
        'payback_reached_in_period': payback_date is not None,
        'cumulative_savings_series': series,
    }
