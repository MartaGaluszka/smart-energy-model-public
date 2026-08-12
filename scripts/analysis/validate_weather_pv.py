"""
Walidacja: Open-Meteo (radiacja, zachmurzenie) vs rzeczywista produkcja PV z FoxESS.

Domyślny okres: od 2025-06-01 (FOXESS_RELIABLE_START, okno ML/RF) do dziś.

Uruchomienie:
    source venv/bin/activate
    python scripts/analysis/validate_weather_pv.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from src.data.household_context import FOXESS_RELIABLE_START, PV_INVERTER_MISCONFIG_END
from src.data.weather_api import (
    flag_likely_fog_days,
    load_daily_pv,
    load_daily_pv_daytime,
    load_daily_weather,
)

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'data/energy_model.db')
START = os.getenv('WEATHER_VALIDATE_START', FOXESS_RELIABLE_START.isoformat())
END = os.getenv('WEATHER_VALIDATE_END', date.today().isoformat())
LOCATION = os.getenv('WEATHER_LOCATION')

PV_NOTE = (
    'FoxESS zapisuje ujemne generationPower przy imporcie z sieci i ładowaniu baterii '
    '(konwencja falownika, nie brak słońca). Do korelacji z pogodą używamy pv_kwh_solar.'
)

FOG_NOTE = (
    'Dni mgłowe: wysoka wilgotność + model radiacji zawyża vs PV (heurystyka). '
    'UWAGA: używa pv_kwh_daytime (agregacja 9-16h). '
    'Po dodaniu pól mgły uruchom ponownie: python scripts/fetch_weather.py'
)

DISPLAY_COLS = ['day', 'pv_kwh_solar', 'pv_kwh', 'pv_kwh_artifact',
                'radiation_kwh_m2', 'cloud_cover_avg']
COL_LABELS = {
    'pv_kwh_solar': 'pv_solar',
    'pv_kwh': 'pv_surowe',
    'pv_kwh_artifact': 'artefakt',
    'radiation_kwh_m2': 'radiacja',
    'cloud_cover_avg': 'chmury_%',
}

FOG_COLS = [
    'day', 'pv_kwh_daytime', 'radiation_daytime_kwh_m2', 'humidity_daytime_avg',
    'cloud_cover_low_avg', 'visibility_min_m', 'yield_kwh_per_kwh_m2', 'likely_fog_day',
]
FOG_LABELS = {
    'pv_kwh_daytime': 'pv_9_16_agg',  # agregacja historyczna
    'radiation_daytime_kwh_m2': 'rad_9_16_agg',
    'humidity_daytime_avg': 'wilg_9_16_avg',
    'cloud_cover_low_avg': 'chm_niskie',
    'visibility_min_m': 'widoczn_m',
    'yield_kwh_per_kwh_m2': 'yield',
    'likely_fog_day': 'mgla',
}


def _format_table(df):
    return df[DISPLAY_COLS].rename(columns=COL_LABELS)


def _format_fog(df):
    cols = [c for c in FOG_COLS if c in df.columns]
    out = df[cols].copy()
    if 'likely_fog_day' in out.columns:
        out['likely_fog_day'] = out['likely_fog_day'].map({True: 'tak', False: 'nie'})
    return out.rename(columns=FOG_LABELS)


def main():
    weather = load_daily_weather(DB_PATH, START, END, LOCATION)
    pv = load_daily_pv(DB_PATH, START, END)
    pv_day = load_daily_pv_daytime(DB_PATH, START, END)

    if weather.empty:
        print('❌ Brak danych w weather_data. Uruchom: python scripts/fetch_weather.py')
        sys.exit(1)
    if pv.empty:
        print('❌ Brak danych PV w foxess_data.')
        sys.exit(1)

    merged = weather.merge(pv, on='day', how='inner')
    if len(merged) < 5:
        print(f'⚠️  Tylko {len(merged)} wspólnych dni — potrzebujesz fetch_weather + dane FoxESS.')
        sys.exit(1)

    has_fog_cols = 'humidity_daytime_avg' in weather.columns and weather['humidity_daytime_avg'].notna().any()
    fog_df = flag_likely_fog_days(weather, pv_day) if has_fog_cols else None

    pv_col = 'pv_kwh_solar'
    corr_rad = merged[pv_col].corr(merged['radiation_kwh_m2'])
    corr_cloud = merged[pv_col].corr(-merged['cloud_cover_avg'])

    p30 = merged[pv_col].quantile(0.30)
    cloudy = merged['cloud_cover_avg'] > 70
    low_pv = merged[pv_col] < p30
    hits = ((cloudy & low_pv) | (~cloudy & ~low_pv)).sum()
    accuracy = hits / len(merged) * 100

    n_artifact_days = (merged['pv_kwh_artifact'] > 0.5).sum()

    print('=' * 70)
    print('Walidacja pogody vs produkcja PV (FoxESS)')
    print(f'Okres: {START} – {END} | dni wspólne: {len(merged)}')
    if START < PV_INVERTER_MISCONFIG_END.isoformat():
        print('⚠️  Uwaga: okres obejmuje 21.04–29.05.2025 — wtedy PV było limitowane')
        print('   pojemnością baterii (błędne ustawienia falownika), nie pogodą.')
    print('=' * 70)
    print(f'Korelacja PV (słońce) ↔ suma radiacji (Open-Meteo):  {corr_rad:.3f}')
    print(f'Korelacja PV (słońce) ↔ (−zachmurzenie):               {corr_cloud:.3f}')
    print(f'Zgodność „pochmurno ↔ niski PV” (prosta reguła):        {accuracy:.1f}%')
    print(f'  (pochmurność > 70% vs PV < {p30:.1f} kWh/dzień, 30. percentyl)')
    print()
    print('Średnie dzienne:')
    print(f'  PV (słońce):     {merged["pv_kwh_solar"].mean():.1f} kWh')
    print(f'  PV (surowe):     {merged["pv_kwh"].mean():.1f} kWh')
    print(f'  Artefakt import: {merged["pv_kwh_artifact"].mean():.1f} kWh')
    print(f'  Radiacja:        {merged["radiation_kwh_m2"].mean():.2f} kWh/m²')
    print(f'  Zachmurzenie:    {merged["cloud_cover_avg"].mean():.0f}%')
    print()
    print(f'📌 Ujemne PV (surowe): {n_artifact_days} dni z artefaktem > 0,5 kWh')
    print(f'   {PV_NOTE}')

    if fog_df is not None and not fog_df.empty:
        n_fog = int(fog_df['likely_fog_day'].sum())
        print()
        print(f'🌫️  Podejrzenie mgły (model zawyża radiację vs PV): {n_fog} dni')
        print(f'   {FOG_NOTE}')
        flagged = fog_df[fog_df['likely_fog_day']].sort_values(
            ['radiation_daytime_kwh_m2', 'pv_kwh_daytime'],
            ascending=[False, True],
        )
        if not flagged.empty:
            print()
            print('TOP dni mgły — radiacja wysoka, PV niskie (agregacja 9-16h):')
            print(_format_fog(flagged.head(15)).to_string(index=False))
            out_path = os.getenv(
                'FOG_REPORT_CSV',
                'data/processed/fog_days_report.csv',
            )
            os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
            flagged_out = flagged.copy()
            flagged_out['likely_fog_day'] = 1
            flagged_out.to_csv(out_path, index=False)
            print(f'   Zapisano raport: {out_path}')
        for check in ('2025-12-13', '2025-12-15'):
            row = fog_df[fog_df['day'] == check]
            if not row.empty:
                r = row.iloc[0]
                print(
                    f'   {check}: mgła={("tak" if r["likely_fog_day"] else "nie")}, '
                    f'PV (agregacja 9-16h)={r["pv_kwh_daytime"]:.1f} kWh, '
                    f'rad (agregacja 9-16h)={r["radiation_daytime_kwh_m2"]:.2f} kWh/m², '
                    f'wilg={r["humidity_daytime_avg"]:.0f}%'
                )
    else:
        print()
        print('🌫️  Brak kolumn mgły w bazie — uruchom: python scripts/fetch_weather.py')

    print()
    print('Top 5 dni — największa produkcja PV (słońce):')
    print(_format_table(merged.nlargest(5, 'pv_kwh_solar')).to_string(index=False))
    print()
    print('Top 5 dni — najniższa produkcja PV (słońce, sprawdź pogodę):')
    print(_format_table(merged.nsmallest(5, 'pv_kwh_solar')).to_string(index=False))
    artifact_days = merged[merged['pv_kwh_artifact'] > 0.5]
    if not artifact_days.empty:
        print()
        print('Dni z dużym artefaktem importu (surowe PV << PV słońce):')
        print(_format_table(
            artifact_days.nsmallest(5, 'pv_kwh')
        ).to_string(index=False))
    print()
    rf_hint = '✅' if corr_rad >= 0.7 else '⚠️'
    print(f'{rf_hint} Korelacja radiacji > 0,7 = dobry sygnał pod RF (Random Forest) i decyzje o ładowaniu baterii.')


if __name__ == '__main__':
    main()
