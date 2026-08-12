#!/usr/bin/env python
"""
Automatyczny tuning Random Forest — silna regularyzacja, minimalizacja gapu.

Strategia wyboru modelu:
  1. GridSearchCV + GroupKFold (MAE na walidacji)
  2. Spośród kandydatów w tolerancji CV wybierz ten z NAJNIŻSZYM gap (test MAE − train MAE)
  3. Przy remisie — niższy test MAE

Dane: FoxESS pvPower (foxess_timeseries), dynamiczne wschód/zachód, BEZ filtra baterii.

Uruchomienie:
    python scripts/train_hourly_model_tuning.py
    python scripts/train_hourly_model_tuning.py --features extended
    python scripts/train_hourly_model_tuning.py --compare
"""

from __future__ import annotations

import argparse
import json
import os

os.makedirs('docs', exist_ok=True)
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold, train_test_split
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt

from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_CS4,
    HOURLY_FEATURE_COLUMNS_CS4_WITH_PANEL,
    HOURLY_FEATURE_COLUMNS_EXTENDED,
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    HOURLY_FEATURE_COLUMNS_WITH_PANEL,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.ml_train_window import format_train_window, resolve_train_window
from src.models.pv_hourly_predictor import (
    DEFAULT_MODEL_PATH,
    PVHourlyPredictor,
    TrainingReport,
    _metrics,
    _overfit_verdict,
)

MLFLOW_EXPERIMENT = 'pv-hourly-forecast'


def _log_to_mlflow(
    *,
    feature_key: str,
    spec: dict,
    feature_columns,
    best: dict,
    rf: dict,
    cv_mean: float,
    cv_std: float,
    verdict: str,
    train_start: str,
    train_end: str,
    summary_path: str,
    grid_path: str,
) -> None:
    """Loguje run treningowy do MLflow (Lekcja 39) — porównanie zestawów cech
    na WSPÓLNEJ metodyce (ten sam GridSearch, ten sam split), zamiast ręcznego
    zestawiania osobnych CSV per feature-set (jak dotychczas w tym skrypcie)."""
    import mlflow
    import mlflow.sklearn

    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name=feature_key):
        mlflow.log_params({
            'feature_set': feature_key,
            'feature_set_label': spec['label'],
            'n_features': len(feature_columns),
            'features': ','.join(feature_columns),
            'model_type': 'random_forest',
            'train_start': train_start,
            'train_end': train_end,
            'split_random_state': SPLIT_RANDOM_STATE,
            'cv_tolerance': CV_TOLERANCE,
            **{f'rf_{k}': v for k, v in rf.items()},
        })
        mlflow.set_tag('model_type', 'random_forest')
        mlflow.log_metrics({
            'train_mae': best['train_mae'],
            'train_r2': best['train_r2'],
            'test_mae': best['test_mae'],
            'test_r2': best['test_r2'],
            'gap': best['gap'],
            'cv_mae': cv_mean,
            'cv_std': cv_std,
            'daily_mae': best['daily_mae'],
            'daily_r2': best['daily_r2'],
        })
        mlflow.set_tag('verdict', verdict)
        mlflow.log_artifact(summary_path)
        mlflow.log_artifact(grid_path)
        mlflow.sklearn.log_model(best['pipeline'], name='model')

# Tolerancja względem najlepszego CV MAE — kandydaci „bliscy optimum”
CV_TOLERANCE = 0.05  # 5%
SPLIT_RANDOM_STATE = 42

PARAM_GRID = {
    'model__max_depth': [6, 8, 10],
    'model__min_samples_leaf': [10, 15, 20],
    'model__min_samples_split': [20, 30, 40],
    'model__max_features': ['sqrt', 'log2', 1.0],
    'model__n_estimators': [200],
}

FEATURE_SETS = {
    'production': {
        'columns': HOURLY_FEATURE_COLUMNS_PRODUCTION,
        'label': '16 cech (PRODUCTION)',
        'default_model_path': DEFAULT_MODEL_PATH,
    },
    'cs4': {
        'columns': HOURLY_FEATURE_COLUMNS_CS4,
        'label': 'CS4 (16 + low/mid + clearness)',
        'default_model_path': 'models/pv_hourly_model_cs4.joblib',
    },
    'extended': {
        'columns': HOURLY_FEATURE_COLUMNS_EXTENDED,
        'label': '19 cech (EXTENDED + kalendarz)',
        'default_model_path': 'models/pv_hourly_model_19.joblib',
    },
    'panel': {
        'columns': HOURLY_FEATURE_COLUMNS_WITH_PANEL,
        'label': '16 + geometria paneli (tilt/azymut)',
        'default_model_path': 'models/pv_hourly_model_panel.joblib',
    },
    'cs4_panel': {
        'columns': HOURLY_FEATURE_COLUMNS_CS4_WITH_PANEL,
        'label': 'CS4 (19) + geometria paneli',
        'default_model_path': 'models/pv_hourly_model_cs4_panel.joblib',
    },
}

COMPARE_CSV = 'data/processed/features_16_vs_19_comparison.csv'
COMPARE_SPLIT_JSON = 'data/processed/features_16_vs_19_split.json'


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', RandomForestRegressor(random_state=42, n_jobs=-1)),
    ])


def _extract_rf_params(pipeline: Pipeline) -> dict:
    m = pipeline.named_steps['model']
    return {
        'n_estimators': m.n_estimators,
        'max_depth': m.max_depth,
        'min_samples_leaf': m.min_samples_leaf,
        'min_samples_split': m.min_samples_split,
        'max_features': m.max_features,
    }


def _evaluate_candidate(
    params: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    meta_test: pd.DataFrame,
) -> dict:
    pipe = _make_pipeline()
    pipe.set_params(**params)
    pipe.fit(X_train, y_train)

    train_pred = pipe.predict(X_train)
    test_pred = pipe.predict(X_test)
    train_m = _metrics(y_train, train_pred)
    test_m = _metrics(y_test, test_pred)
    gap = test_m['mae'] - train_m['mae']

    test_with_pred = meta_test.copy()
    test_with_pred['y_true'] = y_test.values
    test_with_pred['y_pred'] = test_pred
    daily_true = test_with_pred.groupby('day')['y_true'].sum()
    daily_pred = test_with_pred.groupby('day')['y_pred'].sum()
    daily_mae = mean_absolute_error(daily_true, daily_pred)
    daily_r2 = r2_score(daily_true, daily_pred)

    return {
        'pipeline': pipe,
        'params': params,
        'train_mae': train_m['mae'],
        'train_r2': train_m['r2'],
        'test_mae': test_m['mae'],
        'test_r2': test_m['r2'],
        'gap': gap,
        'daily_mae': daily_mae,
        'daily_r2': daily_r2,
    }


def load_training_frame(
    latitude: float,
    longitude: float,
    train_start: str,
    train_end: str,
) -> pd.DataFrame:
    print('\n[1] Ładowanie danych...')
    print(f'[1] GPS instalacji: ~{latitude:.2f}°N, ~{longitude:.2f}°E')
    frame = load_hourly_training_frame_extended(
        start_date=train_start,
        end_date=train_end,
        latitude=latitude,
        longitude=longitude,
    )
    print(f'[1] Okno treningowe: {train_start} – {train_end}')
    print(f'✓ {len(frame)} rekordów, {frame["day"].nunique()} dni')
    if frame.empty:
        raise ValueError(
            f'Brak danych treningowych w oknie {train_start} – {train_end}. '
            'Uruchom sync_data.py lub sprawdź ML_TRAIN_START/ML_TRAIN_END.'
        )
    return frame


def split_frame(
    frame: pd.DataFrame,
    train_start: str,
    train_end: str,
    *,
    save_viz: bool = True,
) -> tuple[pd.DataFrame, ...]:
    print('\n[1.5] Tasowanie danych (Shuffling dni)...')
    unique_days = frame['day'].unique()
    if len(unique_days) < 2:
        raise ValueError(
            f'Za mało dni ({len(unique_days)}) do podziału train/test. '
            'Sprawdź okno treningowe i dane w bazie.'
        )
    train_days, test_days = train_test_split(
        unique_days,
        test_size=0.2,
        random_state=SPLIT_RANDOM_STATE,
        shuffle=True,
    )

    if save_viz:
        plt.figure(figsize=(12, 2))
        plt.scatter(pd.to_datetime(train_days), [1] * len(train_days), label='Train (80%)', alpha=0.5, s=10)
        plt.scatter(pd.to_datetime(test_days), [1] * len(test_days), label='Test (20%)', alpha=0.5, s=10)
        plt.tight_layout()
        plt.xlim(pd.to_datetime(train_start), pd.to_datetime(train_end))
        plt.title(f'Podział 80/20 (Shuffle) | {train_start} → {train_end}')
        plt.legend()
        plt.savefig('reports/figures/data_split_viz.png')
        plt.close()

    train_mask = frame['day'].isin(train_days)
    test_mask = frame['day'].isin(test_days)
    return frame, train_days, test_days, train_mask, test_mask


def run_tuning(
    feature_key: str,
    frame: pd.DataFrame,
    train_mask: pd.Series,
    test_mask: pd.Series,
    *,
    train_start: str,
    train_end: str,
    latitude: float,
    longitude: float,
    save_model: bool = True,
    model_path: str | None = None,
    verbose_grid: int = 1,
    log_mlflow: bool = False,
) -> dict:
    if feature_key not in FEATURE_SETS:
        raise ValueError(f'Nieznany zestaw cech: {feature_key}')

    spec = FEATURE_SETS[feature_key]
    feature_columns = spec['columns']
    model_path = model_path or spec['default_model_path']

    print('\n' + '=' * 72)
    print(f'TUNING RF — {spec["label"]}')
    print('=' * 72)

    n_combos = int(np.prod([len(v) for v in PARAM_GRID.values()]))
    print(f'Siatka: {n_combos} kombinacji × GroupKFold(n=5)')
    print(f'Kryterium końcowe: min gap (w tolerancji CV ±{CV_TOLERANCE:.0%})')
    print(f'Cechy: {len(feature_columns)}')

    X_train = frame.loc[train_mask, feature_columns]
    y_train = frame.loc[train_mask, TARGET_COLUMN]
    X_test = frame.loc[test_mask, feature_columns]
    y_test = frame.loc[test_mask, TARGET_COLUMN]
    groups = frame.loc[train_mask, 'day']
    meta_test = frame.loc[test_mask, ['day', 'hour']]

    print(f'Train: {len(y_train)} h ({groups.nunique()} dni)')
    print(f'Test:  {len(y_test)} h ({meta_test["day"].nunique()} dni)')

    print('\n[2] GridSearchCV (GroupKFold, scoring=neg_MAE)...')
    gkf = GroupKFold(n_splits=5)
    grid = GridSearchCV(
        estimator=_make_pipeline(),
        param_grid=PARAM_GRID,
        cv=gkf,
        scoring='neg_mean_absolute_error',
        refit=False,
        n_jobs=-1,
        verbose=verbose_grid,
    )
    grid.fit(X_train, y_train, groups=groups)

    cv_results = pd.DataFrame(grid.cv_results_)
    cv_results['cv_mae'] = -cv_results['mean_test_score']
    cv_results['cv_mae_std'] = cv_results['std_test_score']

    best_cv_mae = cv_results['cv_mae'].min()
    cv_threshold = best_cv_mae * (1 + CV_TOLERANCE)
    shortlist_idx = cv_results.index[cv_results['cv_mae'] <= cv_threshold].tolist()
    print(f'\n   Najlepsze CV MAE: {best_cv_mae:.3f} kWh/h')
    print(f'   Kandydaci w tolerancji ({len(shortlist_idx)}/{len(cv_results)}): '
          f'CV MAE ≤ {cv_threshold:.3f}')

    print('\n[3] Ocena kandydatów na zbiorze train/test (wybór min gap)...')
    candidates = []
    for idx in shortlist_idx:
        params = grid.cv_results_['params'][idx]
        cv_mae = cv_results.loc[idx, 'cv_mae']
        ev = _evaluate_candidate(params, X_train, y_train, X_test, y_test, meta_test)
        ev['cv_mae'] = cv_mae
        candidates.append(ev)

    candidates.sort(key=lambda c: (c['gap'], c['test_mae']))
    best = candidates[0]

    print('\n   Top 5 kandydatów (sortowanie: gap ↑, test MAE ↑):')
    print(f'   {"max_d":>5} {"min_leaf":>8} {"min_split":>9} {"max_feat":>8} '
          f'{"CV MAE":>7} {"Tr MAE":>7} {"Te MAE":>7} {"Gap":>6} {"R²tr":>6} {"R²te":>6}')
    print('   ' + '-' * 78)
    for c in candidates[:5]:
        p = c['params']
        mf = p['model__max_features']
        mf_s = f'{mf:.1f}' if isinstance(mf, float) else str(mf)
        print(
            f'   {p["model__max_depth"]:>5} {p["model__min_samples_leaf"]:>8} '
            f'{p["model__min_samples_split"]:>9} {mf_s:>8} '
            f'{c["cv_mae"]:>7.3f} {c["train_mae"]:>7.3f} {c["test_mae"]:>7.3f} '
            f'{c["gap"]:>6.3f} {c["train_r2"]:>6.3f} {c["test_r2"]:>6.3f}'
        )

    rf = _extract_rf_params(best['pipeline'])
    print('\n[4] Wybrany model (najmniejszy gap):')
    print(f'   max_depth={rf["max_depth"]}, min_samples_leaf={rf["min_samples_leaf"]}, '
          f'min_samples_split={rf["min_samples_split"]}, max_features={rf["max_features"]}')
    print(f'   Train MAE: {best["train_mae"]:.3f} kWh/h, R²={best["train_r2"]:.3f}')
    print(f'   Test  MAE: {best["test_mae"]:.3f} kWh/h, R²={best["test_r2"]:.3f}')
    print(f'   Gap:       {best["gap"]:.3f} kWh/h ({best["gap"] / best["test_mae"] * 100:.1f}% test MAE)')
    print(f'   CV  MAE:   {best["cv_mae"]:.3f} kWh/h')
    print(f'   Dzienny MAE: {best["daily_mae"]:.3f} kWh/dzień, R²={best["daily_r2"]:.3f}')

    test_minus_cv = best['test_mae'] - best['cv_mae']
    verdict = _overfit_verdict(best['gap'], test_minus_cv, best['test_mae'])
    print(f'   {verdict}')

    print('\n[5] Cross-validation wybranego modelu...')
    cv_scores = []
    for fold, (tr, va) in enumerate(gkf.split(X_train, y_train, groups=groups), 1):
        fold_pipe = clone(best['pipeline'])
        fold_pipe.fit(X_train.iloc[tr], y_train.iloc[tr])
        val_pred = fold_pipe.predict(X_train.iloc[va])
        mae = mean_absolute_error(y_train.iloc[va], val_pred)
        cv_scores.append(mae)
        print(f'   Fold {fold}: MAE={mae:.3f} kWh/h')
    cv_mean = float(np.mean(cv_scores))
    cv_std = float(np.std(cv_scores))
    print(f'   CV średnie: {cv_mean:.3f} ± {cv_std:.3f} kWh/h')

    saved_path = None
    if save_model:
        print('\n[6] Zapis modelu .joblib...')
        predictor = PVHourlyPredictor(model_path=model_path)
        predictor.feature_columns = list(feature_columns)
        predictor.pipeline = best['pipeline']
        predictor.latitude = latitude
        predictor.longitude = longitude
        predictor.location = os.getenv('WEATHER_LOCATION')
        predictor.report = TrainingReport(
            train_mae=best['train_mae'],
            test_mae=best['test_mae'],
            gap=best['gap'],
            cv_mae=cv_mean,
            cv_std=cv_std,
            test_minus_cv=best['test_mae'] - cv_mean,
            daily_mae=best['daily_mae'],
            daily_r2=best['daily_r2'],
            verdict=verdict,
            n_train=len(y_train),
            n_test=len(y_test),
        )
        saved_path = predictor.save(extra_metadata={
            'feature_set': feature_key,
            'train_start': train_start,
            'train_end': train_end,
            'split_random_state': SPLIT_RANDOM_STATE,
            'tuning_strategy': 'hourly_gridsearch_min_gap',
            'target': TARGET_COLUMN,
        })
        print(f'✓ {saved_path}')
        print(f'✓ {saved_path.replace(".joblib", ".metadata.json")}')
    else:
        print('\n[6] Pominięto zapis modelu (--no-save)')

    os.makedirs('data/processed', exist_ok=True)
    summary_suffix = feature_key
    summary = pd.DataFrame([{
        'feature_set': feature_key,
        'n_features': len(feature_columns),
        'model': 'hourly_gridsearch_min_gap',
        **{f'rf_{k}': v for k, v in rf.items()},
        'train_mae_hour': best['train_mae'],
        'train_r2_hour': best['train_r2'],
        'test_mae_hour': best['test_mae'],
        'test_r2_hour': best['test_r2'],
        'gap': best['gap'],
        'gap_pct_of_test': best['gap'] / best['test_mae'] * 100,
        'cv_mae_grid': best['cv_mae'],
        'cv_mae_refold': cv_mean,
        'cv_std': cv_std,
        'daily_mae': best['daily_mae'],
        'daily_r2': best['daily_r2'],
        'verdict': verdict,
        'cv_tolerance': CV_TOLERANCE,
        'split_random_state': SPLIT_RANDOM_STATE,
        'train_start': train_start,
        'train_end': train_end,
    }])
    summary_path = f'data/processed/hourly_model_tuning_summary_{summary_suffix}.csv'
    summary.to_csv(summary_path, index=False)
    print(f'✓ {summary_path}')

    grid_export = []
    for c in candidates:
        p = c['params']
        grid_export.append({
            'feature_set': feature_key,
            'max_depth': p['model__max_depth'],
            'min_samples_leaf': p['model__min_samples_leaf'],
            'min_samples_split': p['model__min_samples_split'],
            'max_features': p['model__max_features'],
            'cv_mae': c['cv_mae'],
            'train_mae': c['train_mae'],
            'test_mae': c['test_mae'],
            'gap': c['gap'],
            'train_r2': c['train_r2'],
            'test_r2': c['test_r2'],
            'selected': c is best,
        })
    grid_path = f'data/processed/hourly_model_grid_search_{summary_suffix}.csv'
    pd.DataFrame(grid_export).sort_values(['gap', 'test_mae']).to_csv(grid_path, index=False)
    print(f'✓ {grid_path}')

    if log_mlflow:
        print('\n[7] Logowanie do MLflow...')
        _log_to_mlflow(
            feature_key=feature_key,
            spec=spec,
            feature_columns=feature_columns,
            best=best,
            rf=rf,
            cv_mean=cv_mean,
            cv_std=cv_std,
            verdict=verdict,
            train_start=train_start,
            train_end=train_end,
            summary_path=summary_path,
            grid_path=grid_path,
        )
        print(f'✓ Zalogowano run "{feature_key}" do eksperymentu "{MLFLOW_EXPERIMENT}"')

    return {
        'feature_set': feature_key,
        'n_features': len(feature_columns),
        'label': spec['label'],
        'train_mae': best['train_mae'],
        'train_r2': best['train_r2'],
        'test_mae': best['test_mae'],
        'test_r2': best['test_r2'],
        'gap': best['gap'],
        'cv_mae': cv_mean,
        'cv_std': cv_std,
        'daily_mae': best['daily_mae'],
        'daily_r2': best['daily_r2'],
        'verdict': verdict,
        'model_path': saved_path,
        **{f'rf_{k}': v for k, v in rf.items()},
    }


def run_compare(
    train_start: str,
    train_end: str,
    *,
    save_models: bool = True,
    verbose_grid: int = 1,
    log_mlflow: bool = False,
    feature_keys: tuple[str, ...] = ('production', 'extended'),
) -> pd.DataFrame:
    """Uczciwe porównanie 16 vs 19 cech — ten sam split i ta sama siatka GridSearch."""
    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))

    print('=' * 72)
    print('PORÓWNANIE OFFLINE: 16 vs 19 CECH (ten sam split 80/20, ta sama siatka RF)')
    print('=' * 72)

    frame = load_training_frame(latitude, longitude, train_start, train_end)
    frame, train_days, test_days, train_mask, test_mask = split_frame(
        frame, train_start, train_end, save_viz=True,
    )

    os.makedirs('data/processed', exist_ok=True)
    split_meta = {
        'random_state': SPLIT_RANDOM_STATE,
        'train_start': train_start,
        'train_end': train_end,
        'train_days': sorted(str(d) for d in train_days),
        'test_days': sorted(str(d) for d in test_days),
        'n_train_days': int(len(train_days)),
        'n_test_days': int(len(test_days)),
    }
    with open(COMPARE_SPLIT_JSON, 'w', encoding='utf-8') as f:
        json.dump(split_meta, f, indent=2, ensure_ascii=False)
    print(f'✓ Split zapisany: {COMPARE_SPLIT_JSON}')

    results = []
    for key in feature_keys:
        results.append(
            run_tuning(
                key,
                frame,
                train_mask,
                test_mask,
                train_start=train_start,
                train_end=train_end,
                latitude=latitude,
                longitude=longitude,
                save_model=save_models,
                verbose_grid=verbose_grid,
                log_mlflow=log_mlflow,
            )
        )

    comparison = pd.DataFrame(results)
    comparison['winner_test_mae'] = comparison['test_mae'] == comparison['test_mae'].min()
    comparison.to_csv(COMPARE_CSV, index=False)
    print('\n' + '=' * 72)
    print('PODSUMOWANIE PORÓWNANIA')
    print('=' * 72)
    print(comparison[[
        'label', 'n_features', 'train_mae', 'test_mae', 'train_r2', 'test_r2',
        'gap', 'cv_mae', 'daily_mae', 'daily_r2', 'winner_test_mae',
    ]].to_string(index=False))
    print(f'\n✓ {COMPARE_CSV}')
    return comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Tuning RF godzinowego (GridSearch + min gap)')
    parser.add_argument(
        '--features',
        choices=sorted(FEATURE_SETS),
        default='production',
        help=(
            'Zestaw cech: production=16, cs4=19 (low/mid+clearness), extended=19 kalendarz, '
            'panel=16+geometria paneli, cs4_panel=CS4+geometria paneli'
        ),
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Porównaj kilka zestawów cech na tym samym splicie (zapis CSV porównawczy)',
    )
    parser.add_argument(
        '--compare-features',
        default='production,extended',
        help='Lista zestawów cech do --compare, po przecinku (np. production,cs4)',
    )
    parser.add_argument(
        '--mlflow',
        action='store_true',
        help='Zaloguj run(y) do MLflow (eksperyment "pv-hourly-forecast", lokalnie ./mlruns)',
    )
    parser.add_argument(
        '--model-path',
        default=None,
        help='Ścieżka zapisu .joblib (domyślnie zależna od --features)',
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Nie nadpisuj pliku .joblib (tylko metryki CSV)',
    )
    parser.add_argument(
        '--grid-verbose',
        type=int,
        default=1,
        help='Poziom verbose GridSearchCV (0=cicho)',
    )
    parser.add_argument(
        '--train-start',
        default=None,
        help='Początek okna (domyślnie auto: rolling 12 mies. od train-end)',
    )
    parser.add_argument(
        '--train-end',
        default=None,
        help='Koniec okna (domyślnie auto: wczoraj / ostatni dzień w bazie)',
    )
    parser.add_argument(
        '--train-months',
        type=int,
        default=None,
        help='Długość okna rolling w miesiącach po fazie expanding (domyślnie 24)',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    train_start, train_end = resolve_train_window(
        train_start=args.train_start,
        train_end=args.train_end,
        rolling_window_months=args.train_months,
    )
    print(f'Okno treningowe: {format_train_window(train_start, train_end)} | shuffle 80/20')

    if args.compare:
        feature_keys = tuple(k.strip() for k in args.compare_features.split(',') if k.strip())
        run_compare(
            train_start,
            train_end,
            save_models=not args.no_save,
            verbose_grid=args.grid_verbose,
            log_mlflow=args.mlflow,
            feature_keys=feature_keys,
        )
        print('\n' + '=' * 72)
        print('GOTOWE — porównanie 16 vs 19 cech zapisane.')
        print('=' * 72)
        return

    latitude = float(os.getenv('WEATHER_LAT', '50.06'))
    longitude = float(os.getenv('WEATHER_LON', '19.94'))

    frame = load_training_frame(latitude, longitude, train_start, train_end)
    _, _, _, train_mask, test_mask = split_frame(
        frame, train_start, train_end, save_viz=True,
    )

    run_tuning(
        args.features,
        frame,
        train_mask,
        test_mask,
        train_start=train_start,
        train_end=train_end,
        latitude=latitude,
        longitude=longitude,
        save_model=not args.no_save,
        model_path=args.model_path,
        verbose_grid=args.grid_verbose,
        log_mlflow=args.mlflow,
    )

    print('\n' + '=' * 72)
    print('GOTOWE — model o najmniejszym gapie zapisany.')
    print('=' * 72)


if __name__ == '__main__':
    main()
