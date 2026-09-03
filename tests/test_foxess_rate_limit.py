"""T1.10 — mapowanie limitu FoxESS 40402 na FOXESS_RATE_LIMIT (bez wywołania API)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.errors import ApiError
from api.services.foxess_sync import (
    FOXESS_RATE_LIMIT_CODE,
    FOXESS_RATE_LIMIT_HINT,
    is_fox_rate_limit,
    sync_range,
)


def test_is_fox_rate_limit_detects_40402():
    assert is_fox_rate_limit(RuntimeError('FoxESS zwraca limit zapytań (40402) — odczekaj'))
    assert is_fox_rate_limit(RuntimeError('limit API FoxESS'))
    assert not is_fox_rate_limit(RuntimeError('Brak FOXESS_API_KEY w .env'))


def test_sync_range_maps_40402_to_429():
    with patch('api.services.foxess_sync.get_settings') as settings:
        settings.return_value.DATABASE_PATH = ':memory:'
        with patch('src.data.foxess_fetch_all.fetch_all', side_effect=RuntimeError(
            'Nie można załadować urządzenia. FoxESS zwraca limit zapytań (40402).'
        )):
            with pytest.raises(ApiError) as exc:
                sync_range('2026-09-01', '2026-09-03')
    assert exc.value.status_code == 429
    assert exc.value.code == FOXESS_RATE_LIMIT_CODE
    assert '40402' in exc.value.detail
    assert '30–60 min' in FOXESS_RATE_LIMIT_HINT
