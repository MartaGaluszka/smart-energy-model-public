"""Kalkulator ROI: przegląd z parametrów, jeden rachunek za cały okres, depozyt proporcjonalnie."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.errors import ApiError
from api.services.roi_service import _deposit_for_slice, calculate_roi


def _bill(savings: float) -> dict:
    return {'savings_gross_pln': savings}


def test_review_stays_the_yearly_amount_and_bill_is_counted_once():
    """Długi okres nie rozciąga przeglądu (kiedyś 120 zł/rok wychodziło 165,70)."""
    assumptions = {'capex_pln': 10000.0, 'opex_pln_year': 120.0, 'inflation_pct': 0.0}

    with patch('api.services.bill_simulator.simulate_bill', return_value=_bill(450.0)) as bill, patch(
        'api.services.roi_service._deposit_for_slice', side_effect=[10.0, 20.0]
    ) as deposit:
        out = calculate_roi('2025-06-01', '2025-07-15', assumptions, db=None, user_id=2)

    bill.assert_called_once_with('2025-06-01', '2025-07-15', db=None, user_id=2)
    assert deposit.call_count == 2
    assert out['savings_pln_period'] == 450.0
    assert out['opex_pln_period'] == 120.0
    assert out['deposit_pln_period'] == 30.0
    assert out['cash_gain_pln_period'] == 360.0
    # Dalsze punkty serii to już projekcja poza okresem, aż do zwrotu.
    observed = [row for row in out['cumulative_savings_series'] if row['year'] <= 2]
    assert observed[-1]['cumulative_savings_pln'] == 360.0
    assert out['payback_reached_in_period'] is False
    assert out['remaining_pln'] == 9640.0


def test_payback_inside_the_period_caps_recovered_at_capex():
    assumptions = {'capex_pln': 200.0, 'opex_pln_year': 120.0}

    with patch('api.services.bill_simulator.simulate_bill', return_value=_bill(1000.0)), patch(
        'api.services.roi_service._deposit_for_slice', return_value=0.0
    ):
        out = calculate_roi('2025-06-01', '2025-06-30', assumptions, db=None, user_id=2)

    assert out['cash_gain_pln_period'] == 880.0
    assert out['recovered_pln'] == 200.0
    assert out['remaining_pln'] == 0.0
    assert out['payback_reached_in_period'] is True
    assert out['remaining_years'] == 0.0


def test_period_end_before_start_is_rejected():
    with pytest.raises(ApiError) as caught:
        calculate_roi('2025-07-01', '2025-06-01', {'capex_pln': 1, 'opex_pln_year': 120}, db=None, user_id=2)
    assert caught.value.status_code == 422
    assert caught.value.code == 'ROI_INVALID_PERIOD'


def test_bill_failure_is_wrapped():
    with patch('api.services.bill_simulator.simulate_bill', side_effect=RuntimeError('pusto')), pytest.raises(
        ApiError
    ) as caught:
        calculate_roi('2025-06-01', '2025-06-30', {'opex_pln_year': 120}, db=None, user_id=2)
    assert caught.value.code == 'ROI_CALCULATE_FAILED'


def test_deposit_of_a_full_month_is_not_cut_and_a_partial_month_is():
    summary = SimpleNamespace(net_deposit_accrual_pln=310.0)
    with patch(
        'src.financial.prosumer_deposit.calculate_prosumer_deposit_rcem', return_value=summary
    ) as rcem:
        full = _deposit_for_slice('/tmp/db', '2025-06', '2025-06-01', '2025-06-30')
        part = _deposit_for_slice('/tmp/db', '2026-10', '2026-10-01', '2026-10-17')

    assert rcem.call_count == 2
    assert full == 310.0
    assert part == pytest.approx(310.0 * 17 / 31)
