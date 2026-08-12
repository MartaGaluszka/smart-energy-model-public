#!/usr/bin/env python
"""Zbuduj profil błędu operacyjnego z forecast_validation_hourly.csv."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    from src.models.forecast_error_profile import build_error_profile, profile_summary

    profile = build_error_profile()
    print(profile_summary(profile))
    print(f'Zapisano: data/processed/forecast_error_profile.csv ({len(profile)} godzin)')


if __name__ == '__main__':
    main()
