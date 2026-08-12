"""
FoxESS — odczyt i sterowanie baterią (ForceCharge, tryb pracy, min SoC).

Wymaga FOXESS_API_KEY (i opcjonalnie FOXESS_DEVICE_SN) w .env.
Używa biblioteki foxesscloud (te same endpointy co aplikacja FoxESS Cloud).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import foxesscloud.openapi as foxess
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class ForceChargeWindow:
    enabled: bool
    start_hour: float
    end_hour: float

    def label(self) -> str:
        if not self.enabled:
            return 'wyłączone'
        return f'{_fmt_hour(self.start_hour)}–{_fmt_hour(self.end_hour)}'


@dataclass
class BatteryControlState:
    device_sn: str | None
    work_mode: str | None
    force_charge_1: ForceChargeWindow
    force_charge_2: ForceChargeWindow
    min_soc: float | None
    min_soc_on_grid: float | None
    schedule_enabled: bool | None

    def summary_lines(self) -> list[str]:
        lines = [
            f'Urządzenie: {self.device_sn or "?"}',
            f'Tryb pracy: {self.work_mode or "?"}',
            f'ForceCharge okno 1: {self.force_charge_1.label()}',
            f'ForceCharge okno 2: {self.force_charge_2.label()}',
        ]
        if self.min_soc is not None or self.min_soc_on_grid is not None:
            lines.append(
                f'Min SoC: {self.min_soc if self.min_soc is not None else "?"}% '
                f'(on-grid: {self.min_soc_on_grid if self.min_soc_on_grid is not None else "?"}%)'
            )
        if self.schedule_enabled is not None:
            lines.append(f'Harmonogram FoxESS: {"włączony" if self.schedule_enabled else "wyłączony"}')
        return lines


def _fmt_hour(h: float) -> str:
    hour = int(h) % 24
    minute = int(round((h - int(h)) * 60))
    if minute >= 60:
        hour = (hour + 1) % 24
        minute = 0
    return f'{hour:02d}:{minute:02d}'


def _time_dict_to_hours(value: dict | None) -> float:
    if not value:
        return 0.0
    return float(value.get('hour', 0)) + float(value.get('minute', 0)) / 60.0


def _parse_force_window(times: dict | None, prefix: str) -> ForceChargeWindow:
    times = times or {}
    enabled = bool(times.get(f'enable{prefix}'))
    start = _time_dict_to_hours(times.get(f'startTime{prefix}'))
    end = _time_dict_to_hours(times.get(f'endTime{prefix}'))
    return ForceChargeWindow(enabled=enabled, start_hour=start, end_hour=end)


class FoxEssControl:
    """Sterowanie baterią przez FoxESS Open API."""

    def __init__(self, api_key: str | None = None, device_sn: str | None = None):
        load_dotenv()
        raw_key = api_key or os.getenv('FOXESS_API_KEY') or os.getenv('FOXESS_TOKEN')
        self.api_key = (raw_key or '').strip().strip('"').strip("'")
        self.device_sn = device_sn or os.getenv('FOXESS_DEVICE_SN') or None
        if self.device_sn == '':
            self.device_sn = None

        if not self.api_key:
            raise ValueError(
                'Brak FOXESS_API_KEY w .env (User Profile → API Management).'
            )

        foxess.api_key = self.api_key
        if self.device_sn:
            foxess.device_sn = self.device_sn
        foxess.debug_setting = int(os.getenv('FOXESS_DEBUG', '0'))

    def _ensure_device(self) -> str | None:
        device = foxess.get_device()
        if not device:
            return None
        sn = device.get('deviceSN') or device.get('sn')
        if sn:
            self.device_sn = sn
            foxess.device_sn = sn
        return sn

    def read_state(self) -> BatteryControlState:
        sn = self._ensure_device()
        charge = foxess.get_charge() or {}
        times = charge.get('times') if charge else None
        min_settings = foxess.get_min() or {}
        work_mode = foxess.get_work_mode()
        schedule = foxess.get_schedule() or {}

        return BatteryControlState(
            device_sn=sn,
            work_mode=work_mode,
            force_charge_1=_parse_force_window(times, '1'),
            force_charge_2=_parse_force_window(times, '2'),
            min_soc=min_settings.get('minSoc'),
            min_soc_on_grid=min_settings.get('minSocOnGrid'),
            schedule_enabled=schedule.get('enable'),
        )

    def set_force_charge_windows(
        self,
        *,
        period1: ForceChargeWindow | None = None,
        period2: ForceChargeWindow | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        current = self.read_state()
        p1 = period1 or current.force_charge_1
        p2 = period2 or current.force_charge_2

        payload = {
            'period1': {
                'enabled': p1.enabled,
                'start': p1.start_hour,
                'end': p1.end_hour,
            },
            'period2': {
                'enabled': p2.enabled,
                'start': p2.start_hour,
                'end': p2.end_hour,
            },
        }
        if dry_run:
            logger.info('[DRY-RUN] set_force_charge_windows: %s', payload)
            return {'dry_run': True, 'action': 'set_force_charge_windows', **payload}

        self._ensure_device()
        result = foxess.set_charge(
            ch1=p1.enabled,
            st1=p1.start_hour,
            en1=p1.end_hour,
            ch2=p2.enabled,
            st2=p2.start_hour,
            en2=p2.end_hour,
            enable=1,
        )
        if result is None:
            raise RuntimeError('FoxESS set_charge() nie powiodło się — sprawdź log / harmonogram.')
        return {'dry_run': False, 'action': 'set_force_charge_windows', **payload}

    def set_work_mode(self, mode: str, *, dry_run: bool = True, force: int = 0) -> dict[str, Any]:
        payload = {'mode': mode}
        if dry_run:
            logger.info('[DRY-RUN] set_work_mode: %s', mode)
            return {'dry_run': True, 'action': 'set_work_mode', **payload}

        self._ensure_device()
        result = foxess.set_work_mode(mode, force=force)
        if result is None:
            raise RuntimeError(f'FoxESS set_work_mode({mode}) nie powiodło się.')
        return {'dry_run': False, 'action': 'set_work_mode', **payload}

    def set_min_soc(
        self,
        *,
        min_soc: float | None = None,
        min_soc_on_grid: float | None = None,
        dry_run: bool = True,
        force: int = 0,
    ) -> dict[str, Any]:
        payload = {'min_soc': min_soc, 'min_soc_on_grid': min_soc_on_grid}
        if dry_run:
            logger.info('[DRY-RUN] set_min_soc: %s', payload)
            return {'dry_run': True, 'action': 'set_min_soc', **payload}

        self._ensure_device()
        result = foxess.set_min(minSoc=min_soc, minSocOnGrid=min_soc_on_grid, force=force)
        if result is None:
            raise RuntimeError('FoxESS set_min() nie powiodło się.')
        return {'dry_run': False, 'action': 'set_min_soc', **payload}
