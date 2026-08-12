"""
Kalibracja modelu topnienia śniegu + porównanie z regułą 7d/3°C.

Model: temperatura + pokrywa śnieżna + wilgotność → bilans S_t → godzina startu PV.
Kalibracja na proxy PV (bez etykiet foto). Zdjęcia — tylko walidacja.

UWAGA: Używa pv_kwh_daytime (suma 9-16h, agregacja historyczna) jako proxy.
       Model topnienia przewiduje godzinową produkcję (dynamiczne okno 5-20h).

Uruchomienie:
    python scripts/calibrate_snow_melt.py
    python scripts/calibrate_snow_melt.py --no-calibrate
    python scripts/calibrate_snow_melt.py --csv data/processed/snow_melt_comparison.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.photo_ground_truth import CLASS_GROUPS, GROUND_TRUTH_CLASS
from src.data.weather_api import load_daily_pv, load_daily_pv_daytime, load_daily_weather
from src.features.snow_melt_model import (
    SnowMeltParams,
    build_melt_daily_frame,
    calibrate_snow_melt_params,
    compare_snow_rules,
    load_hourly_weather_pv,
    simulate_hourly_snow,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
LOCATION = os.getenv('WEATHER_LOCATION')
OUT_CSV = os.getenv('SNOW_MELT_CSV', 'data/processed/snow_melt_comparison.csv')
OUT_RANK = os.getenv('SNOW_MELT_RANK_CSV', 'data/processed/snow_melt_calibration.csv')
OUT_PNG = os.getenv('SNOW_MELT_PNG', 'reports/figures/snow_melt_27_28_nov.png')

# Współrzędne dla dynamicznych godzin wschodu/zachodu
LATITUDE = float(os.getenv('WEATHER_LAT', '50.06'))
LONGITUDE = float(os.getenv('WEATHER_LON', '19.94'))


def _snow_block_from_gt(gt: str) -> int | None:
    if gt == 'artifact':
        return None
    grp = CLASS_GROUPS.get(gt, '')
    if grp == 'snow_block':
        return 1
    if grp == 'snow_landscape':
        return 0
    return None


def _plot_transition(
    hourly_sim: pd.DataFrame,
    day_before: str,
    day_after: str,
    out_path: str,
) -> None:
    sub = hourly_sim[hourly_sim['day'].isin([day_before, day_after])].copy()
    if sub.empty:
        return

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=False)
    for ax, day, title in zip(
        axes,
        [day_before, day_after],
        [f'{day_before} (blokada)', f'{day_after} (odsłonięcie)'],
    ):
        g = sub[sub['day'] == day].sort_values('hour')
        ax2 = ax.twinx()
        ax.fill_between(g['hour'], 0, g['snow_roof_cm'], alpha=0.25, color='steelblue', label='śnieg na dachu [cm]')
        ax.plot(g['hour'], g['snow_roof_cm'], color='steelblue', lw=2)
        ax2.bar(g['hour'], g['pv_kwh'], alpha=0.5, color='orange', width=0.7, label='PV [kWh/h]')
        ax.set_ylabel('śnieg [cm]')
        ax2.set_ylabel('PV [kWh/h]')
        ax.set_xlabel('godzina')
        ax.set_title(title)
        ax.set_xlim(5, 19)
        ax.grid(alpha=0.3)
    fig.suptitle('Model topnienia: przejście blokada → produkcja', fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f'📈 Wykres: {out_path}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Kalibracja modelu topnienia śniegu')
    parser.add_argument('--start', default=os.getenv('ML_TRAIN_START', '2025-06-01'))
    parser.add_argument('--end', default=os.getenv('ML_TRAIN_END', '2026-06-30'))
    parser.add_argument('--no-calibrate', action='store_true', help='Użyj domyślnych parametrów bez grida')
    parser.add_argument('--csv', default=OUT_CSV, help='CSV porównania dziennego')
    args = parser.parse_args()

    weather = load_daily_weather(DB_PATH, args.start, args.end, LOCATION)
    pv = load_daily_pv(DB_PATH, args.start, args.end)
    pv_day = load_daily_pv_daytime(DB_PATH, args.start, args.end)
    daily = weather.merge(pv, on='day').merge(pv_day, on='day')
    daily.rename(columns={'snowfall_cm_sum': 'om_snowfall_cm'}, inplace=True)

    if args.no_calibrate:
        params = SnowMeltParams(
            latitude=LATITUDE,
            longitude=LONGITUDE,
            use_dynamic_hours=True
        )
        ranking = pd.DataFrame()
        print('❄️ Model topnienia: parametry domyślne (bez kalibracji)')
        print(f'   Lokalizacja: {LATITUDE}°N, {LONGITUDE}°E')
        print('   Używam dynamicznych godzin wschodu/zachodu słońca')
    else:
        print('❄️ Kalibracja modelu topnienia (grid, proxy PV)...')
        print(f'   Lokalizacja: {LATITUDE}°N, {LONGITUDE}°E')
        print('   Używam dynamicznych godzin wschodu/zachodu słońca')
        params, ranking = calibrate_snow_melt_params(daily, latitude=LATITUDE, longitude=LONGITUDE)
        print(f'   Wybrane: T_melt={params.t_melt_c}°C, k_melt={params.k_melt_cm_per_h}, slide={params.slide_fraction}')
        if not ranking.empty:
            os.makedirs(os.path.dirname(OUT_RANK) or '.', exist_ok=True)
            ranking.to_csv(OUT_RANK, index=False)
            print(f'   Ranking: {OUT_RANK}')
            print(ranking.head(5).to_string(index=False))

    melt_daily = build_melt_daily_frame(DB_PATH, args.start, args.end, LOCATION, params=params)
    compared = compare_snow_rules(daily, melt_daily)

    os.makedirs(os.path.dirname(args.csv) or '.', exist_ok=True)
    compared.to_csv(args.csv, index=False)
    print(f'\n💾 Porównanie dzienne: {args.csv} ({len(compared)} dni)')

    winter = compared[pd.to_datetime(compared['day']).dt.month.isin([11, 12, 1, 2, 3])]
    if not winter.empty:
        agree = winter['snow_rules_agree'].mean()
        legacy_days = winter['snow_on_panels'].sum()
        melt_days = winter['snow_on_panels_melt'].sum()
        print(f'\n📊 Zima (XI–III): zgodność reguł legacy vs melt: {100 * agree:.0f}%')
        print(f'   Dni snow_on_panels legacy: {int(legacy_days)}')
        print(f'   Dni snow_on_panels melt:   {int(melt_days)}')

    # Walidacja foto
    photo_rows = []
    for day in sorted(GROUND_TRUTH_CLASS):
        gt = GROUND_TRUTH_CLASS[day]
        expected = _snow_block_from_gt(gt)
        if expected is None:
            continue
        row = compared[compared['day'] == day]
        if row.empty:
            continue
        r = row.iloc[0]
        photo_rows.append({
            'day': day,
            'ground_truth': gt,
            'expected_blocked': expected,
            'legacy_blocked': int(r['snow_on_panels']),
            'melt_blocked': int(r['snow_on_panels_melt']),
            'legacy_ok': int(r['snow_on_panels'] == expected),
            'melt_ok': int(r['snow_on_panels_melt'] == expected),
            'pv_kwh_daytime': r.get('pv_kwh_daytime'),
            'snow_roof_cm': r.get('snow_roof_cm_prod_hours') or r.get('snow_roof_cm_9_16'),
            'pv_start_pred': r.get('pv_start_hour_pred'),
            'pv_start_obs': r.get('pv_start_hour_obs'),
        })
    photo_df = pd.DataFrame(photo_rows)
    if not photo_df.empty:
        n = len(photo_df)
        leg = photo_df['legacy_ok'].sum()
        mel = photo_df['melt_ok'].sum()
        print(f'\n📷 Walidacja foto (Typ A vs B, N={n}, bez artifact):')
        print(f'   Reguła legacy 7d/3°C: {leg}/{n} ({100 * leg / n:.0f}%)')
        print(f'   Model topnienia:      {mel}/{n} ({100 * mel / n:.0f}%)')

        start_cmp = photo_df.dropna(subset=['pv_start_pred', 'pv_start_obs'])
        if len(start_cmp) >= 3:
            mae = (start_cmp['pv_start_pred'] - start_cmp['pv_start_obs']).abs().mean()
            print(f'   MAE godziny startu PV (foto-dni): {mae:.1f} h')

    # Przykład 27→28 XI
    hourly = load_hourly_weather_pv(DB_PATH, '2025-11-25', '2025-11-30', LOCATION)
    if not hourly.empty:
        sim = simulate_hourly_snow(hourly, params=params)
        _plot_transition(sim, '2025-11-27', '2025-11-28', OUT_PNG)

    # Przykładowe dni z rozmowy
    for label, d in [('27.11', '2025-11-27'), ('28.11', '2025-11-28'), ('21.01', '2026-01-21')]:
        r = compared[compared['day'] == d]
        if r.empty:
            continue
        x = r.iloc[0]
        # Wybierz kolumnę śniegu (nowa lub stara)
        snow_col = 'snow_roof_cm_prod_hours' if 'snow_roof_cm_prod_hours' in x else 'snow_roof_cm_9_16'
        print(
            f'\n🔎 {label}: PV (agregacja 9-16h)={x.get("pv_kwh_daytime", 0):.1f} kWh | '
            f'legacy={int(x["snow_on_panels"])} melt={int(x["snow_on_panels_melt"])} | '
            f'śnieg (godz. produkcji)={x.get(snow_col, 0):.2f} cm | '
            f'start PV pred/obs={x.get("pv_start_hour_pred")}/{x.get("pv_start_hour_obs")}'
        )


if __name__ == '__main__':
    main()
