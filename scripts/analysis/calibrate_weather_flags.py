"""
Kalibracja heurystyk pogoda/PV na dniach z obserwacjami foto (klasy jakościowe).

Porównuje:
  - ground truth (GROUND_TRUTH_CLASS z photo_ground_truth.py)
  - predict_pv_day_class() — reguły radiacja + yield + śnieg
  - flag_likely_fog_days() — mgła
  - find_snow_pv_loss_days — kandydaci Typ A (śnieg na panelach)

Uruchomienie:
    python scripts/calibrate_weather_flags.py
    python scripts/calibrate_weather_flags.py --csv data/processed/calibration_photo_days.csv
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

_snow_mod_path = os.path.join(os.path.dirname(__file__), 'find_snow_pv_loss_days.py')
_spec = importlib.util.spec_from_file_location('find_snow_pv_loss_days', _snow_mod_path)
_snow_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_snow_mod)
build_winter_table = _snow_mod.build_winter_table

from src.data.photo_ground_truth import (
    CLASS_GROUPS,
    DEFAULT_PHOTO_VALIDATION,
    GROUND_TRUTH_CLASS,
    PV_CORRECTION_FACTOR,
    PHOTO_METADATA,
    class_group,
    ground_truth_for_day,
    parse_photo_validation,
)
from src.data.weather_api import (
    flag_likely_fog_days,
    load_daily_pv,
    load_daily_pv_daytime,
    load_daily_weather,
    predict_pv_day_class,
    winter_reference_yield,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
LOCATION = os.getenv('WEATHER_LOCATION')


def _load_imgw(db_path: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        '''
        SELECT day, snow_depth_cm AS imgw_snow_depth_cm
        FROM imgw_daily WHERE day BETWEEN ? AND ?
        ''',
        conn,
        params=(start, end),
    )
    conn.close()
    return df


def build_calibration_table(db_path: str, days: list[str]) -> pd.DataFrame:
    start, end = min(days), max(days)

    weather = load_daily_weather(db_path, start, end, LOCATION)
    pv = load_daily_pv(db_path, start, end)
    pv_day = load_daily_pv_daytime(db_path, start, end)
    imgw = _load_imgw(db_path, start, end)

    merged = weather.merge(pv, on='day').merge(pv_day, on='day').merge(imgw, on='day', how='left')
    merged.rename(columns={
        'snowfall_cm_sum': 'om_snowfall_cm',
        'radiation_daytime_kwh_m2': 'rad_9_16_agg',  # agregacja historyczna
    }, inplace=True)
    merged['om_snow_depth_cm'] = (merged['snow_depth_m_max'].fillna(0) * 100).round(0)

    ref_yield = winter_reference_yield(weather, pv_day, pv)
    fog = flag_likely_fog_days(weather, pv_day)
    fog_map = fog.set_index('day')['likely_fog_day'].to_dict()

    try:
        winter = build_winter_table(db_path, start, end, LOCATION)
        snow_cand = set(
            winter[
                winter['is_sunny'] & winter['low_vs_expected']
                & winter['snow_context'] & winter['foxess_clean']
            ]['day']
        )
    except ValueError:
        snow_cand = set()

    rows = []
    for day in sorted(days):
        if day not in merged['day'].values:
            continue
        row = merged[merged['day'] == day].iloc[0]
        gt = ground_truth_for_day(day)
        meta = PHOTO_METADATA.get(day, {})

        pred = predict_pv_day_class(
            row,
            ref_yield_kwh_per_kwh_m2=ref_yield,
            likely_fog=bool(fog_map.get(day, False)),
        )
        fog_flag = bool(fog_map.get(day, False))
        snow_flag = day in snow_cand

        rows.append({
            'day': day,
            'ground_truth': gt,
            'gt_group': class_group(gt),
            'predicted': pred,
            'pred_group': class_group(pred),
            'exact_match': gt == pred,
            'group_match': class_group(gt) == class_group(pred),
            'likely_fog_flag': fog_flag,
            'snow_candidate_flag': snow_flag,
            'pv_correction_factor': PV_CORRECTION_FACTOR.get(pred, 1.0),
            'pv_kwh_daytime': row.get('pv_kwh_daytime'),
            'rad_9_16_agg_kwh_m2': row.get('rad_9_16_agg'),  # agregacja historyczna
            'om_snow_depth_cm': row.get('om_snow_depth_cm'),
            'imgw_snow_depth_cm': row.get('imgw_snow_depth_cm'),
            'photo_sky': meta.get('photo_sky'),
            'photo_snow_cm': meta.get('photo_snow_cm'),
        })

    return pd.DataFrame(rows)


def _print_metrics(df: pd.DataFrame) -> None:
    eval_df = df[df['ground_truth'] != 'artifact'].copy()
    n = len(eval_df)
    if n == 0:
        print('Brak dni do oceny.')
        return

    exact = eval_df['exact_match'].sum()
    group = eval_df['group_match'].sum()
    print(f'\n📊 Trafność reguł predict_pv_day_class ({n} dni, bez artifact):')
    print(f'   Dokładna klasa:  {exact}/{n} ({100 * exact / n:.0f}%)')
    print(f'   Grupa (sky/snieg): {group}/{n} ({100 * group / n:.0f}%)')

    fog_days = eval_df[eval_df['ground_truth'] == 'fog']
    if len(fog_days):
        hit = fog_days['likely_fog_flag'].sum()
        print(f'\n🌫️  flag_likely_fog_days vs ground truth „fog”: {hit}/{len(fog_days)}')

    block_days = eval_df[eval_df['ground_truth'] == 'snow_panel_block']
    if len(block_days):
        hit = block_days['snow_candidate_flag'].sum()
        pred_hit = (block_days['predicted'] == 'snow_panel_block').sum()
        print(f'\n❄️  Typ A (snow_panel_block):')
        print(f'   snow_candidate (find_snow): {hit}/{len(block_days)}')
        print(f'   predict_pv_day_class:       {pred_hit}/{len(block_days)}')

    landscape = eval_df[eval_df['ground_truth'] == 'snow_landscape']
    if len(landscape):
        pred_hit = (landscape['predicted'] == 'snow_landscape').sum()
        false_block = (landscape['predicted'] == 'snow_panel_block').sum()
        print(f'\n🏠 Typ B (snow_landscape): predict={pred_hit}/{len(landscape)}, '
              f'fałszywy Typ A={false_block}')

    misses = eval_df[~eval_df['exact_match']][
        ['day', 'ground_truth', 'predicted', 'pv_kwh_daytime', 'rad_9_16_agg_kwh_m2', 'photo_sky']
    ]
    if not misses.empty:
        print('\n⚠️  Rozbieżności (ground truth ≠ predicted):')
        print(misses.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description='Kalibracja heurystyk na dniach z foto')
    parser.add_argument(
        '--csv',
        default=os.getenv('CALIBRATION_CSV', 'data/processed/calibration_photo_days.csv'),
        help='Ścieżka CSV wyjściowego',
    )
    args = parser.parse_args()

    raw = os.getenv('PHOTO_VALIDATION', DEFAULT_PHOTO_VALIDATION)
    days = [d for d, _ in parse_photo_validation(raw)]

    print('=' * 72)
    print('Kalibracja heurystyk pogoda/PV vs obserwacje foto (klasy jakościowe)')
    print(f'Dni w PHOTO_VALIDATION: {len(days)}')
    print('=' * 72)

    df = build_calibration_table(DB_PATH, days)
    if df.empty:
        print('❌ Brak danych w bazie dla podanych dat.')
        sys.exit(1)

    show = df.copy()
    show['exact_match'] = show['exact_match'].map({True: '✓', False: '✗'})
    show['group_match'] = show['group_match'].map({True: '✓', False: '✗'})
    cols = [
        'day', 'ground_truth', 'predicted', 'exact_match', 'group_match',
        'pv_kwh_daytime', 'rad_9_16_agg_kwh_m2', 'pv_correction_factor',
        'likely_fog_flag', 'snow_candidate_flag',
    ]
    print(show[cols].to_string(index=False))

    _print_metrics(df)

    os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
    df.to_csv(args.csv, index=False)
    print(f'\n✅ Zapisano: {args.csv}')
    print('\n💡 Klasy ground truth w src/data/photo_ground_truth.py — bez % chmur z foto.')


if __name__ == '__main__':
    main()
