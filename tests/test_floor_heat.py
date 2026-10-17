"""Detektor bufora podłogi: plateau ~3 kW zostaje, czajnik i zmywarka odpadają."""

from datetime import datetime, timedelta

from src.features.floor_heat import detect_floor_heat_cycles


def _at(hour: int, minute: int, power: float) -> tuple[datetime, float]:
    return datetime(2026, 10, 17, hour, minute), power


def test_night_plateau_is_a_cycle_and_kettle_is_not():
    samples = [
        _at(1, 28, 0.14),
        _at(1, 33, 1.45),
        _at(1, 38, 3.12),
        _at(1, 42, 3.27),
        _at(1, 47, 3.38),
        _at(1, 51, 3.22),
        _at(1, 56, 0.18),
        _at(10, 38, 0.19),
        _at(10, 42, 5.09),
        _at(10, 47, 0.89),
    ]
    cycles = detect_floor_heat_cycles(samples)
    assert len(cycles) == 1
    assert cycles[0].started_at == datetime(2026, 10, 17, 1, 33)
    assert cycles[0].peak_kw == 3.38
    assert 0.5 <= cycles[0].kwh <= 1.3
    assert cycles[0].ongoing is False


def test_dishwasher_and_drill_are_not_floor_heat():
    samples = [
        _at(11, 28, 0.14),
        _at(11, 32, 2.08),
        _at(11, 37, 2.13),
        _at(11, 46, 2.14),
        _at(11, 50, 0.17),
        _at(12, 8, 2.18),
        _at(12, 12, 3.50),
        _at(12, 17, 4.33),
        _at(12, 21, 1.12),
        _at(12, 26, 0.24),
    ]
    assert detect_floor_heat_cycles(samples) == []


def test_open_cycle_at_the_end_stays_ongoing():
    start = datetime(2026, 10, 17, 16, 34)
    samples = [(start, 0.13)]
    for step, power in enumerate((0.95, 2.05, 2.67, 2.83, 2.93, 3.06, 3.23), start=1):
        samples.append((start + timedelta(minutes=5 * step), power))
    cycles = detect_floor_heat_cycles(samples)
    assert len(cycles) == 1
    assert cycles[0].ongoing is True
    assert cycles[0].peak_kw == 3.23
