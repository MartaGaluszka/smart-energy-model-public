"""Retry Open-Meteo GET przy chwilowym DNS (launchd 05:00)."""

from __future__ import annotations

import socket
import urllib.error

from src.data import weather_api


class _OkResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"ok": true}'


def test_get_json_retries_after_dns_then_succeeds(monkeypatch):
    calls = {'n': 0}

    def fake_urlopen(_url, timeout=120):
        calls['n'] += 1
        if calls['n'] < 3:
            raise urllib.error.URLError(socket.gaierror(8, 'nodename nor servname provided, or not known'))
        return _OkResponse()

    monkeypatch.setattr(weather_api.urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setattr(weather_api.time, 'sleep', lambda _s: None)

    out = weather_api._get_json('https://example.test/v1', {'a': 1}, retries=4, backoff_s=0.01)
    assert out == {'ok': True}
    assert calls['n'] == 3


def test_get_json_raises_after_retries(monkeypatch):
    def fake_urlopen(_url, timeout=120):
        raise urllib.error.URLError(socket.gaierror(8, 'nodename nor servname provided, or not known'))

    monkeypatch.setattr(weather_api.urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setattr(weather_api.time, 'sleep', lambda _s: None)

    try:
        weather_api._get_json('https://example.test/v1', {}, retries=2, backoff_s=0.01)
        raise AssertionError('expected URLError')
    except urllib.error.URLError:
        pass
