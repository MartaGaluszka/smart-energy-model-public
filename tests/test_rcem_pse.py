"""Parser tabeli RCEm z pse.pl i okno korekty (12 miesięcy)."""

from datetime import date

import pytest

from src.data.rcem import (
    RcEmNotPublished,
    correction_window_open,
    get_rcem,
    parse_rcem_html,
    previous_calendar_month,
    sync_official_rcem,
)

_HTML = '''
<table>
  <tr><th colspan="4"><strong>2026</strong></th></tr>
  <tr><td colspan="4"><strong>luty</strong></td></tr>
  <tr><td>RCEm</td><td>339,01</td><td>11.03.2026</td><td>-</td></tr>
  <tr><td>skorygowana RCEm*</td><td>331,39</td><td>11.06.2026</td><td>-2,25</td></tr>
  <tr><td colspan="4"><strong>sierpień</strong></td></tr>
  <tr><td>RCEm</td><td><span>294,53</span></td><td>11.09.2026</td><td>-</td></tr>
  <tr><td>skorygowana RCEm*</td><td>-</td><td>-</td><td>-</td></tr>
</table>
<table>
  <tr><th colspan="4"><strong>2024</strong></th></tr>
  <tr><td colspan="4"><strong>maj</strong></td></tr>
  <tr><td>RCEm</td><td>255,59</td><td>11.06.2024</td><td>-</td></tr>
  <tr><td>skorygowana RCEm*</td><td>255,32</td><td>11.07.2024</td><td>-0,11</td></tr>
  <tr><td>skorygowana RCEm*</td><td>254,19</td><td>11.09.2024</td><td>-0,44</td></tr>
  <tr><td colspan="4"><strong>marzec***</strong></td></tr>
  <tr><td>RCEm</td><td>249,12</td><td>11.04.2024</td><td>-</td></tr>
  <tr><td>skorygowana RCEm*</td><td>-</td><td>-</td><td>-</td></tr>
</table>
'''


def test_parse_keeps_latest_correction_and_ignores_dash():
    parsed = parse_rcem_html(_HTML)
    assert parsed['2026-02']['rce_pln_mwh'] == pytest.approx(339.01)
    assert parsed['2026-02']['corrected_rce_pln_mwh'] == pytest.approx(331.39)
    assert parsed['2026-02']['corrected_publication_date'] == '2026-06-11'
    assert 'corrected_rce_pln_mwh' not in parsed['2026-08']
    assert parsed['2026-08']['rce_pln_mwh'] == pytest.approx(294.53)
    assert parsed['2024-05']['corrected_rce_pln_mwh'] == pytest.approx(254.19)
    assert parsed['2024-05']['corrected_publication_date'] == '2024-09-11'
    assert parsed['2024-03']['rce_pln_mwh'] == pytest.approx(249.12)
    assert 'corrected_rce_pln_mwh' not in parsed['2024-03']


def test_correction_window_closes_after_twelve_months():
    assert correction_window_open('2025-10', date(2026, 10, 31))
    assert not correction_window_open('2025-09', date(2026, 10, 1))
    assert previous_calendar_month(date(2026, 10, 11)) == '2026-09'


def test_sync_writes_official_row_and_uses_correction(tmp_path):
    db = tmp_path / 'rcem.db'
    changes = sync_official_rcem(str(db), as_of=date(2026, 10, 1), html=_HTML)
    by_month = {row['period_month']: row['action'] for row in changes}
    assert by_month['2026-02'] == 'inserted'
    assert by_month['2026-08'] == 'inserted'
    assert '2024-05' not in by_month

    stored = get_rcem('2026-02', str(db))
    assert stored['rce_pln_mwh'] == pytest.approx(331.39)
    assert stored['source'] == 'pse_official'
    assert stored['is_corrected'] is True

    again = sync_official_rcem(str(db), as_of=date(2026, 10, 1), html=_HTML)
    assert {row['action'] for row in again} == {'unchanged'}


def test_eleventh_requires_previous_month():
    with pytest.raises(RcEmNotPublished):
        sync_official_rcem(db_path=':memory:', as_of=date(2026, 10, 11), html=_HTML)
