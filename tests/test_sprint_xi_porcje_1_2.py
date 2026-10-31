"""Porcje Sprint XI 1–2 — CLI i integracja lekka (bez Fox Cloud)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_mlops_scripts_expose_evening_context_in_help():
    scripts = (
        'mlops/generate_battery_suggestions.py',
        'mlops/foxess_control.py',
        'mlops/battery_advisor_report.py',
    )
    for rel in scripts:
        proc = subprocess.run(
            [sys.executable, str(ROOT / rel), '--help'],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert 'evening' in proc.stdout
    stop_help = subprocess.run(
        [sys.executable, str(ROOT / 'mlops/foxess_control.py'), '--help'],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert '--stop-fc' in stop_help.stdout
    assert '--no-read-state' in stop_help.stdout


def test_foxess_sync_range_skipped_when_api_paused(monkeypatch):
    monkeypatch.setenv('FOXESS_SYNC_DISABLED', '1')
    monkeypatch.delenv('FOXESS_SYNC_PAUSED_UNTIL', raising=False)

    with patch('src.data.foxess_fetch_all.fetch_all') as fetch:
        from api.services.foxess_sync import sync_range

        out = sync_range('2026-11-01', '2026-11-01')
    fetch.assert_not_called()
    assert out['status'] == 'skipped'
    assert out['days'] == 0
