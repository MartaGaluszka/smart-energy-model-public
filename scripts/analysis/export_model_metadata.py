#!/usr/bin/env python
"""Eksport metadata.json obok istniejącego models/*.joblib (bez retreningu).

Użycie:
    ./venv/bin/python scripts/analysis/export_model_metadata.py
    ./venv/bin/python scripts/analysis/export_model_metadata.py --model models/pv_hourly_model.joblib
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from src.models.pv_hourly_predictor import DEFAULT_MODEL_PATH, PVHourlyPredictor


def main() -> None:
    parser = argparse.ArgumentParser(description='Zapis metadata.json obok .joblib')
    parser.add_argument('--model', default=os.getenv('PV_HOURLY_MODEL_PATH', DEFAULT_MODEL_PATH))
    args = parser.parse_args()

    predictor = PVHourlyPredictor(model_path=args.model)
    predictor.load()
    meta_path = predictor.write_metadata_sidecar()
    print(f'✓ {meta_path}')


if __name__ == '__main__':
    main()
