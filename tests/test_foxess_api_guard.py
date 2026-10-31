"""Pauza FoxESS API — plik / env, bez wywołań chmury."""

from datetime import datetime, timedelta

from src.data.foxess_api_guard import (
    clear_pause,
    is_api_paused,
    pause_file_path,
    set_pause_hours,
)


def test_pause_file_blocks_until_expired(tmp_path, monkeypatch):
    monkeypatch.setenv('FOXESS_PAUSE_FILE', str(tmp_path / 'pause'))
    monkeypatch.delenv('FOXESS_SYNC_DISABLED', raising=False)
    monkeypatch.delenv('FOXESS_SYNC_PAUSED_UNTIL', raising=False)
    clear_pause()
    assert not is_api_paused(now=datetime(2026, 10, 27, 10, 0, 0))
    until = set_pause_hours(24.0, now=datetime(2026, 10, 27, 10, 0, 0))
    assert until == datetime(2026, 10, 28, 10, 0, 0)
    assert is_api_paused(now=datetime(2026, 10, 27, 12, 0, 0))
    assert not is_api_paused(now=datetime(2026, 10, 28, 11, 0, 0))
    assert pause_file_path().is_file()


def test_sync_disabled_env(monkeypatch):
    monkeypatch.setenv('FOXESS_SYNC_DISABLED', '1')
    monkeypatch.delenv('FOXESS_SYNC_PAUSED_UNTIL', raising=False)
    assert is_api_paused()


def test_pause_message_mentions_guard(monkeypatch):
    from src.data.foxess_api_guard import pause_message

    monkeypatch.setenv('FOXESS_SYNC_DISABLED', '1')
    msg = pause_message()
    assert 'FOXESS' in msg.upper() or 'sync' in msg.lower()
