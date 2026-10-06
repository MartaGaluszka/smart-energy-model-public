from datetime import date, datetime
from pathlib import Path

from src.ops.catchup_needed import (
    has_primary_daily,
    has_primary_midday,
    jobs_to_run,
    last_sunday,
    needs_daily_catchup,
    needs_midday_catchup,
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


def test_has_primary_midday_requires_same_run_and_target(tmp_path: Path):
    csv_path = tmp_path / 'h.csv'
    csv_path.write_text(
        'run_at,run_label,target_day\n'
        '2026-10-06T05:00:33,daily,2026-10-06\n'
        '2026-10-06T12:00:37,midday_icon,2026-10-06\n'
        '2026-10-05T12:00:37,midday,2026-10-06\n',
        encoding='utf-8',
    )
    assert has_primary_midday(csv_path, date(2026, 10, 6)) is False

    csv_path.write_text(
        csv_path.read_text(encoding='utf-8') + '2026-10-06T12:00:37,midday,2026-10-06\n',
        encoding='utf-8',
    )
    assert has_primary_midday(csv_path, date(2026, 10, 6)) is True


def test_midday_catchup_window_and_throttle():
    kw = dict(has_midday=False, attempts=0, last_attempt=None)
    # przed 12:20 — daj szansę normalnemu runowi launchd
    assert needs_midday_catchup(now=datetime(2026, 10, 6, 12, 10), **kw) is False
    assert needs_midday_catchup(now=datetime(2026, 10, 6, 12, 50), **kw) is True
    assert needs_midday_catchup(now=datetime(2026, 10, 6, 15, 40), **kw) is True
    # od 15:45 — peak o 16:00, nie udawaj południa
    assert needs_midday_catchup(now=datetime(2026, 10, 6, 15, 45), **kw) is False
    assert needs_midday_catchup(now=datetime(2026, 10, 6, 19, 44), **kw) is False

    now = datetime(2026, 10, 6, 13, 0)
    assert needs_midday_catchup(
        now=now, has_midday=True, attempts=0, last_attempt=None
    ) is False
    assert needs_midday_catchup(
        now=now, has_midday=False, attempts=1, last_attempt=datetime(2026, 10, 6, 12, 50)
    ) is False
    assert needs_midday_catchup(
        now=now, has_midday=False, attempts=4, last_attempt=None
    ) is False


def test_jobs_midday_after_restart():
    jobs = jobs_to_run(
        now=datetime(2026, 10, 6, 12, 55),  # wtorek, train z niedzieli ok
        has_daily=True,
        train_ok_day=date(2026, 10, 4),
        has_midday=False,
    )
    assert jobs == ['midday']


def test_jobs_default_does_not_trigger_midday():
    jobs = jobs_to_run(
        now=datetime(2026, 10, 6, 13, 0),
        has_daily=True,
        train_ok_day=date(2026, 10, 4),
    )
    assert jobs == []
