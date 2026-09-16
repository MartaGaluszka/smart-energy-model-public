"""Kiedy nadrabiać daily 05:00 / weekly train po śnie albo padzie DNS."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

DAILY_CATCHUP_AFTER = (5, 20)
DAILY_CATCHUP_UNTIL = (12, 0)  # potem jest midday — nie udawaj Porannej wieczorem
TRAIN_CATCHUP_AFTER = (4, 35)
MAX_DAILY_ATTEMPTS = 4
MIN_RETRY_MINUTES = 20


def last_sunday(day: date) -> date:
    """Niedziela tego tygodnia (dziś, jeśli niedziela). weekday() pon=0 … nd=6."""
    days_since_sun = (day.weekday() + 1) % 7
    return day - timedelta(days=days_since_sun)


def has_primary_daily(history_csv: Path, day: date) -> bool:
    """Czy forecast_history ma primary `daily` z run_at i target_day = ten dzień."""
    if not history_csv.is_file():
        return False
    day_s = day.isoformat()
    try:
        with history_csv.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if (row.get('run_label') or '').strip() != 'daily':
                    continue
                run_at = (row.get('run_at') or '')[:10]
                target = (row.get('target_day') or '')[:10]
                if run_at == day_s and target == day_s:
                    return True
    except OSError:
        return False
    return False


def needs_weekly_train(train_ok_day: date | None, now: datetime) -> bool:
    sunday = last_sunday(now.date())
    gate = datetime.combine(sunday, datetime.min.time()).replace(
        hour=TRAIN_CATCHUP_AFTER[0],
        minute=TRAIN_CATCHUP_AFTER[1],
    )
    if now < gate:
        return False
    return train_ok_day != sunday


def needs_daily_catchup(
    *,
    has_daily: bool,
    now: datetime,
    attempts: int,
    last_attempt: datetime | None,
) -> bool:
    if has_daily:
        return False
    gate = now.replace(
        hour=DAILY_CATCHUP_AFTER[0],
        minute=DAILY_CATCHUP_AFTER[1],
        second=0,
        microsecond=0,
    )
    if now < gate:
        return False
    until = now.replace(
        hour=DAILY_CATCHUP_UNTIL[0],
        minute=DAILY_CATCHUP_UNTIL[1],
        second=0,
        microsecond=0,
    )
    if now >= until:
        return False
    if attempts >= MAX_DAILY_ATTEMPTS:
        return False
    if last_attempt is not None and (now - last_attempt) < timedelta(minutes=MIN_RETRY_MINUTES):
        return False
    return True


def jobs_to_run(
    *,
    now: datetime,
    has_daily: bool,
    train_ok_day: date | None,
    daily_attempts: int = 0,
    last_daily_attempt: datetime | None = None,
) -> list[str]:
    """Kolejność: train (nowe wagi) przed daily."""
    jobs: list[str] = []
    if needs_weekly_train(train_ok_day, now):
        jobs.append('train')
    if needs_daily_catchup(
        has_daily=has_daily,
        now=now,
        attempts=daily_attempts,
        last_attempt=last_daily_attempt,
    ):
        jobs.append('daily')
    return jobs


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return date.fromisoformat(raw[:10])


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if raw.endswith('Z'):
        raw = raw[:-1]
    return datetime.fromisoformat(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Wypisz joby catch-up (train / daily).')
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--train-marker', type=Path, required=True)
    parser.add_argument('--daily-state', type=Path, default=None)
    parser.add_argument('--now', default=None, help='ISO datetime (testy); domyślnie teraz')
    args = parser.parse_args(argv)

    now = _parse_dt(args.now) or datetime.now()
    train_ok = None
    if args.train_marker.is_file():
        train_ok = _parse_day(args.train_marker.read_text(encoding='utf-8'))

    attempts = 0
    last_attempt = None
    if args.daily_state and args.daily_state.is_file():
        parts = args.daily_state.read_text(encoding='utf-8').strip().split()
        if parts:
            try:
                attempts = int(parts[0])
            except ValueError:
                attempts = 0
        if len(parts) >= 2:
            last_attempt = _parse_dt(parts[1])

    jobs = jobs_to_run(
        now=now,
        has_daily=has_primary_daily(args.history, now.date()),
        train_ok_day=train_ok,
        daily_attempts=attempts,
        last_daily_attempt=last_attempt,
    )
    for job in jobs:
        print(job)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
