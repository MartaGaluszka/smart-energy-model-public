from datetime import date, datetime
from pathlib import Path

from src.ops.catchup_needed import (
    has_primary_daily,
    jobs_to_run,
    last_sunday,
    needs_daily_catchup,
    needs_weekly_train,
)


def test_last_sunday_friday_is_previous():
    assert last_sunday(date(2026, 9, 11)) == date(2026, 9, 6)


def test_last_sunday_on_sunday_is_today():
    assert last_sunday(date(2026, 9, 13)) == date(2026, 9, 13)


def test_has_primary_daily_requires_same_run_and_target(tmp_path: Path):
    csv_path = tmp_path / 'h.csv'
    csv_path.write_text(
        'run_at,run_label,target_day\n'
        '2026-09-11T05:05:16,daily_icon,2026-09-11\n'
        '2026-09-11T12:00:01,daily,2026-09-11\n',
        encoding='utf-8',
    )
    # 12:00 ma label daily — to już jest primary z tego dnia (nietypowe, ale liczy się)
    assert has_primary_daily(csv_path, date(2026, 9, 11)) is True

    csv_path.write_text(
        'run_at,run_label,target_day\n'
        '2026-09-11T05:05:16,daily_icon,2026-09-11\n'
        '2026-09-10T05:00:44,daily,2026-09-11\n',
        encoding='utf-8',
    )
    assert has_primary_daily(csv_path, date(2026, 9, 11)) is False


def test_needs_train_sunday_morning_if_marker_old():
    now = datetime(2026, 9, 13, 10, 0)
    assert needs_weekly_train(date(2026, 9, 6), now) is True
    assert needs_weekly_train(date(2026, 9, 13), now) is False


def test_needs_train_skips_before_gate_on_sunday():
    now = datetime(2026, 9, 13, 4, 20)
    assert needs_weekly_train(date(2026, 9, 6), now) is False


def test_needs_train_monday_if_sunday_missed():
    now = datetime(2026, 9, 14, 8, 0)
    assert needs_weekly_train(date(2026, 9, 6), now) is True


def test_daily_catchup_after_0520_and_throttle():
    now = datetime(2026, 9, 11, 5, 25)
    assert needs_daily_catchup(has_daily=False, now=now, attempts=0, last_attempt=None) is True
    assert needs_daily_catchup(has_daily=True, now=now, attempts=0, last_attempt=None) is False
    assert needs_daily_catchup(
        has_daily=False,
        now=now,
        attempts=1,
        last_attempt=datetime(2026, 9, 11, 5, 10),
    ) is False
    assert needs_daily_catchup(has_daily=False, now=now, attempts=4, last_attempt=None) is False


def test_daily_catchup_stops_at_midday():
    evening = datetime(2026, 9, 11, 21, 17)
    assert needs_daily_catchup(has_daily=False, now=evening, attempts=0, last_attempt=None) is False


def test_jobs_train_before_daily():
    jobs = jobs_to_run(
        now=datetime(2026, 9, 13, 8, 0),
        has_daily=False,
        train_ok_day=date(2026, 9, 6),
        daily_attempts=0,
    )
    assert jobs == ['train', 'daily']
