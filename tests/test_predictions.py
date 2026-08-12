"""Testy warstwy predykcji — ścieżki modelu, ranking godzin, pipeline."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from src.features.pv_features_hourly_extended import HOURLY_FEATURE_COLUMNS_PRODUCTION
from src.models.pv_hourly_predictor import (
    PVHourlyPredictor,
    rank_hours_for_appliances,
    resolve_model_path,
)


class TestModelPaths:
    def test_resolve_model_path_is_absolute_under_project_root(self):
        path = resolve_model_path('models/pv_hourly_model.joblib')
        assert Path(path).is_absolute()
        assert path.endswith('models/pv_hourly_model.joblib')


class TestRankHours:
    def test_rank_hours_picks_top_n_per_day(self):
        preds = pd.DataFrame([
            {'day': '2026-08-01', 'hour': 10, 'predicted_kwh': 1.0, 'prediction_source': 'model'},
            {'day': '2026-08-01', 'hour': 11, 'predicted_kwh': 3.0, 'prediction_source': 'model'},
            {'day': '2026-08-01', 'hour': 12, 'predicted_kwh': 2.0, 'prediction_source': 'model'},
            {'day': '2026-08-01', 'hour': 13, 'predicted_kwh': 0.5, 'prediction_source': 'foxess_actual'},
        ])
        recs = rank_hours_for_appliances(preds, top_n_per_day=2)
        assert len(recs) == 2
        assert recs[0].hour == 11
        assert recs[0].rank == 1
        assert 'Gotowanie' in recs[0].appliances or recs[0].appliances


class TestPredictorPipeline:
    @pytest.fixture
    def tiny_predictor(self, tmp_path):
        rng = np.random.default_rng(42)
        n = 48
        X = pd.DataFrame({
            col: rng.uniform(0, 1, n) for col in HOURLY_FEATURE_COLUMNS_PRODUCTION
        })
        y = rng.uniform(0.5, 4.0, n)

        pipeline = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', RandomForestRegressor(n_estimators=1, max_depth=2, random_state=42)),
        ])
        pipeline.fit(X, y)

        model_path = tmp_path / 'test_pv.joblib'
        joblib.dump({
            'pipeline': pipeline,
            'feature_columns': list(HOURLY_FEATURE_COLUMNS_PRODUCTION),
            'latitude': 50.06,
            'longitude': 19.94,
            'location': 'test',
        }, model_path)

        predictor = PVHourlyPredictor(model_path=str(model_path))
        predictor.load()
        return predictor

    def test_load_restores_sixteen_feature_columns(self, tiny_predictor):
        assert len(tiny_predictor.feature_columns) == 16
        assert list(tiny_predictor.feature_columns) == list(HOURLY_FEATURE_COLUMNS_PRODUCTION)

    def test_pipeline_predict_non_negative_kwh(self, tiny_predictor):
        row = pd.DataFrame([{c: 0.5 for c in tiny_predictor.feature_columns}])
        pred = float(tiny_predictor.pipeline.predict(row)[0])
        assert pred >= 0.0
