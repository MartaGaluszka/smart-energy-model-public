"""Accu reżim + routing CS4 vs ensemble."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.weather.accu_regime import classify_regime_from_accu, pick_model_for_regime
from src.weather.forecast_routing import accu_cs4_routing_enabled, resolve_forecast_display


@pytest.mark.parametrize(
    ('bri', 'cloud', 'precip', 'regime'),
    [
        (2.0, 89.0, 0.0, 'pochmurny'),
        (9.0, 25.0, 0.0, 'jasny'),
        (5.0, 50.0, 0.0, 'mix'),
    ],
)
def test_classify_regime_accu_only(bri, cloud, precip, regime):
    assert (
        classify_regime_from_accu(
            brightness=bri,
            cloud_pct=cloud,
            precip_mm=precip,
            thunder_prob_pct=None,
        )
        == regime
    )


def test_pick_cs4_only_on_pochmurny():
    assert pick_model_for_regime('pochmurny') == 'cs4'
    assert pick_model_for_regime('jasny') == 'ensemble'
    assert pick_model_for_regime('mix') == 'ensemble'


def test_routing_disabled_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('ACCU_CS4_UI', None)
        os.environ.pop('ACCU_CS4_ROUTING', None)
        assert accu_cs4_routing_enabled() is False
        r = resolve_forecast_display('2026-11-01')
        assert r.display_model == 'ensemble'
        assert r.enabled is False


def test_routing_pochmurny_when_flag_and_accu(monkeypatch):
    monkeypatch.setenv('ACCU_CS4_UI', '1')

    class FakeSnap:
        brightness = 2.0
        cloud_pct = 89.0
        precip_mm = 0.0
        precip_prob_pct = 9.0
        thunder_prob_pct = 0.0
        note_kind = 'daily_summary'

        def as_dict(self):
            return {}

    with patch('src.weather.forecast_routing.load_accu_for_target_day', return_value=FakeSnap()):
        r = resolve_forecast_display('2026-11-01')
        assert r.enabled is True
        assert r.regime == 'pochmurny'
        assert r.display_model == 'cs4'
