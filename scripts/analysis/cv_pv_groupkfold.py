"""
Cross-validation PV (dzienny target: pv_kwh_daytime) z GroupKFold.

UWAGA: pv_kwh_daytime to suma 9-16h (historyczna agregacja).
       Dla modelu godzinowego z dynamicznymi godzinami (5-20h) użyj train_hourly_model.py.

Domyślnie grupujemy po miesiącach (całe miesiące w foldach), co lepiej
sprawdza generalizację sezonową (lato/jesień/zima/wiosna).

Uruchomienie:
    source venv/bin/activate
    python scripts/cv_pv_groupkfold.py

Opcje:
    python scripts/cv_pv_groupkfold.py --n-splits 5 --group-by month
    python scripts/cv_pv_groupkfold.py --start 2025-06-01 --end 2026-06-30
    python scripts/cv_pv_groupkfold.py --compare-snow-melt
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, cross_val_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.features.pv_features import (
    DEFAULT_SNOW_THAW_TEMP_C,
    DEFAULT_SNOW_WINDOW_DAYS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    apply_snow_panel_flags,
    load_training_frame,
)
from src.features.snow_melt_model import (
    SnowMeltParams,
    apply_melt_snow_flags,
    calibrate_snow_melt_params,
)


def _make_groups(df: pd.DataFrame, group_by: str) -> pd.Series:
    day = pd.to_datetime(df['day'])
    if group_by == 'month':
        return day.dt.to_period('M').astype(str)
    if group_by == 'season':
        def season(m: int) -> str:
            if m in (12, 1, 2):
                return 'zima'
            if m in (3, 4, 5):
                return 'wiosna'
            if m in (6, 7, 8):
                return 'lato'
            return 'jesień'

        return day.dt.month.map(season)
    raise ValueError(f'Nieznane group_by={group_by!r} (dozwolone: month, season)')


def _snow_logic(
    frame: pd.DataFrame,
    window_days: int,
    thaw_temp_c: float,
) -> pd.DataFrame:
    """Reguła dzienna 7d/3°C (legacy)."""
    if 'temp_max' not in frame.columns:
        raise ValueError("Brak kolumny 'temp_max' w ramce treningowej.")
    if 'om_snowfall_cm' not in frame.columns:
        raise ValueError("Brak kolumny 'om_snowfall_cm' w ramce treningowej.")

    df = frame.copy()
    dt = pd.to_datetime(df['day'])
    df['_dt'] = dt
    df = df.sort_values('_dt').reset_index(drop=True)

    max_temp = df['temp_max'].rolling(window=window_days, min_periods=1).max()
    snow_sum = df['om_snowfall_cm'].fillna(0).rolling(window=window_days, min_periods=1).sum()

    snow_on = ((snow_sum > 0) & (max_temp < thaw_temp_c)).astype(int)
    df['snow_on_panels'] = snow_on
    df['snow_on_panels_prev'] = df['snow_on_panels'].shift(1).fillna(0).astype(int)

    df.drop(columns=['_dt'], inplace=True)
    return df


def _eval_cv(
    frame: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int,
    feature_cols: list[str],
) -> tuple[np.ndarray, float, float]:
    cv = GroupKFold(n_splits=n_splits)
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    scores = cross_val_score(
        model,
        frame[feature_cols],
        y,
        groups=groups,
        cv=cv,
        scoring='neg_mean_absolute_error',
    )
    mae = -scores
    return mae, float(mae.mean()), float(mae.std())


def _eval_cv_nested_melt(
    base_frame: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int,
    feature_cols: list[str],
    *,
    db_path: str,
    location: str | None,
    calibrate_per_fold: bool,
    global_params: SnowMeltParams | None = None,
) -> tuple[np.ndarray, float, float, SnowMeltParams | None]:
    """
    GroupKFold z kalibracją modelu topnienia tylko na train w każdym foldzie.

    Symulacja śniegu jest przyczynowa (godzinowa), więc flagi na teście nie
    widzą przyszłej pogody — tylko parametry topnienia są dopasowywane na train.
    """
    cv = GroupKFold(n_splits=n_splits)
    maes: list[float] = []
    last_params: SnowMeltParams | None = global_params

    start = str(base_frame['day'].min())
    end = str(base_frame['day'].max())

    for train_idx, test_idx in cv.split(base_frame, y, groups):
        train_df = base_frame.iloc[train_idx]
        if calibrate_per_fold:
            melt_params, _ = calibrate_snow_melt_params(train_df)
        else:
            melt_params = global_params or SnowMeltParams()

        fold_frame = apply_melt_snow_flags(
            base_frame, db_path, start, end, location, params=melt_params,
        )
        model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
        model.fit(fold_frame.iloc[train_idx][feature_cols], y.iloc[train_idx])
        pred = model.predict(fold_frame.iloc[test_idx][feature_cols])
        maes.append(float(mean_absolute_error(y.iloc[test_idx], pred)))
        last_params = melt_params

    arr = np.array(maes)
    return arr, float(arr.mean()), float(arr.std()), last_params


def _compare_snow_melt_cv(
    *,
    start: str | None,
    end: str | None,
    group_by: str,
    n_splits: int,
    calibrate_melt_per_fold: bool,
    out_csv: str,
) -> None:
    db_path = os.getenv('DATABASE_PATH', 'data/energy_model.db')
    location = os.getenv('WEATHER_LOCATION')

    base = load_training_frame(
        start_date=start, end_date=end, snow_mode='none',
    )
    if base.empty:
        raise SystemExit('Brak danych (sprawdź ML_TRAIN_START/END).')

    y = base[TARGET_COLUMN]
    groups = _make_groups(base, group_by)
    n_groups = groups.nunique()
    if n_splits > n_groups:
        raise SystemExit(
            f'n_splits={n_splits} > liczba grup={n_groups}. Zmniejsz --n-splits.'
        )

    print('=' * 70)
    print('Porównanie CV: reguła legacy vs model topnienia')
    print(f'Okres: {base["day"].min()} – {base["day"].max()} | dni: {len(base)}')
    print(f'GroupKFold: {n_splits} folds | grupowanie: {group_by} ({n_groups} grup)')
    print('=' * 70)

    legacy_frame = apply_snow_panel_flags(
        base.copy(), DEFAULT_SNOW_WINDOW_DAYS, DEFAULT_SNOW_THAW_TEMP_C,
    )
    mae_l, mean_l, std_l = _eval_cv(legacy_frame, y, groups, n_splits, FEATURE_COLUMNS)
    print('\n[1] Random Forest + reguła legacy (7d / 3°C)')
    print('    MAE per fold [kWh]:', np.round(mae_l, 3))
    print(f'    Średnie MAE: {mean_l:.3f} kWh | std: {std_l:.3f}')

    melt_global_params = None
    if not calibrate_melt_per_fold:
        melt_global_params, rank = calibrate_snow_melt_params(base)
        print('\n    Kalibracja melt (globalna, przed CV):', melt_global_params)

    mae_m, mean_m, std_m, melt_params = _eval_cv_nested_melt(
        base,
        y,
        groups,
        n_splits,
        FEATURE_COLUMNS,
        db_path=db_path,
        location=location,
        calibrate_per_fold=calibrate_melt_per_fold,
        global_params=melt_global_params,
    )
    print('\n[2] Random Forest + model topnienia (melt)')
    if calibrate_melt_per_fold:
        print('    Kalibracja melt: osobno w każdym foldzie (train only)')
    else:
        print('    Kalibracja melt: globalna na całym zbiorze')
    print('    MAE per fold [kWh]:', np.round(mae_m, 3))
    print(f'    Średnie MAE: {mean_m:.3f} kWh | std: {std_m:.3f}')
    if melt_params:
        print(f'    Parametry melt (ostatni fold / global): T={melt_params.t_melt_c}°C, '
              f'k={melt_params.k_melt_cm_per_h}, slide={melt_params.slide_fraction}')

    delta = mean_m - mean_l
    winner = 'melt' if mean_m < mean_l else 'legacy'
    print('\n' + '-' * 70)
    print(f'Różnica średniego MAE (melt − legacy): {delta:+.3f} kWh')
    print(f'Lepszy wariant CV: {winner}')
    print('-' * 70)

    rows = []
    for i, (ml, mm) in enumerate(zip(mae_l, mae_m), start=1):
        rows.append({'fold': i, 'model': 'legacy_7d_3c', 'mae_kwh': ml})
        rows.append({'fold': i, 'model': 'melt_formula', 'mae_kwh': mm})
    summary = pd.DataFrame(rows)
    summary.loc[len(summary)] = {
        'fold': 'mean', 'model': 'legacy_7d_3c', 'mae_kwh': mean_l,
    }
    summary.loc[len(summary)] = {
        'fold': 'mean', 'model': 'melt_formula', 'mae_kwh': mean_m,
    }

    os.makedirs(os.path.dirname(out_csv) or '.', exist_ok=True)
    summary.to_csv(out_csv, index=False)
    print(f'\n💾 Zapisano: {out_csv}')


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=os.getenv('ML_TRAIN_START'))
    parser.add_argument('--end', default=os.getenv('ML_TRAIN_END'))
    parser.add_argument('--group-by', default='month', choices=['month', 'season'])
    parser.add_argument('--n-splits', type=int, default=5)
    parser.add_argument(
        '--snow-grid',
        action='store_true',
        help='Porównaj kilka wariantów logiki śniegu (okno 3/5/7 × próg 1/2/3°C).',
    )
    parser.add_argument(
        '--compare-snow-melt',
        action='store_true',
        help='CV=5 (GroupKFold po miesiącach): reguła legacy vs model topnienia.',
    )
    parser.add_argument(
        '--melt-global-calibration',
        action='store_true',
        help='Kalibruj melt raz na całym zbiorze (domyślnie: per fold na train).',
    )
    parser.add_argument(
        '--out-csv',
        default=os.getenv('CV_SNOW_COMPARE_CSV', 'data/processed/cv_snow_melt_comparison.csv'),
    )
    args = parser.parse_args()

    if args.compare_snow_melt:
        _compare_snow_melt_cv(
            start=args.start,
            end=args.end,
            group_by=args.group_by,
            n_splits=args.n_splits,
            calibrate_melt_per_fold=not args.melt_global_calibration,
            out_csv=args.out_csv,
        )
        return

    frame = load_training_frame(start_date=args.start, end_date=args.end)
    if frame.empty:
        raise SystemExit('Brak danych w ramce treningowej (sprawdź ML_TRAIN_START/END i import pogody/PV).')

    y = frame[TARGET_COLUMN]
    groups = _make_groups(frame, args.group_by)

    n_groups = groups.nunique()
    if args.n_splits > n_groups:
        raise SystemExit(
            f'n_splits={args.n_splits} > liczba grup={n_groups} (group_by={args.group_by}). '
            'Zmniejsz --n-splits lub użyj group_by=month.'
        )

    print('=' * 70)
    print('PV CV (GroupKFold)')
    print(f'Okres danych: {frame["day"].min()} – {frame["day"].max()} | dni: {len(frame)}')
    print(f'Grupowanie: {args.group_by} | grup: {n_groups} | folds: {args.n_splits}')
    print('=' * 70)
    if not args.snow_grid:
        mae, mean_mae, std_mae = _eval_cv(frame, y, groups, args.n_splits, FEATURE_COLUMNS)
        print('MAE per fold [kWh]:', np.round(mae, 3))
        print(f'Średnie MAE: {mean_mae:.3f} kWh | std: {std_mae:.3f}')
        return

    windows = [3, 5, 7]
    thaws = [1.0, 2.0, 3.0]

    rows: list[dict[str, float | int | str]] = []
    for w in windows:
        for t in thaws:
            f2 = _snow_logic(frame, window_days=w, thaw_temp_c=t)
            mae, mean_mae, std_mae = _eval_cv(f2, y, groups, args.n_splits, FEATURE_COLUMNS)
            rows.append(
                {
                    'window_days': w,
                    'thaw_temp_c': t,
                    'mae_mean_kwh': mean_mae,
                    'mae_std_kwh': std_mae,
                }
            )

    out = pd.DataFrame(rows).sort_values(['mae_mean_kwh', 'mae_std_kwh']).reset_index(drop=True)
    print('Ranking wariantów (niższe MAE = lepiej):')
    print(out.to_string(index=False, formatters={'mae_mean_kwh': '{:.3f}'.format, 'mae_std_kwh': '{:.3f}'.format}))


if __name__ == '__main__':
    main()
