#!/usr/bin/env python3
"""
Wykres walidacji prognoz PV — lipiec 2026 (pod prezentację / pracę zaliczeniową).

Pokazuje:
  - Rzeczywistość (PVEnergyTotal) vs raw RF i hybryda dnia (5:00 oraz 12:00)
  - Błąd względny (|APE| %): raw vs hybryda dnia

Uwaga terminologiczna:
  - raw = sam Random Forest na cały dzień
  - hybryda dnia = FoxESS na minione godziny + RF na przyszłe
    (to NIE jest korekta FORECAST_OPERATIONAL_ADJUST)

Źródło: data/processed/forecasts/forecast_validation.csv + weather_data
Wyjście:
  - reports/figures/july_validation_plot.png
  - reports/figures/july_validation_summary.md  (pogoda + kiedy hybryda pomaga/szkodzi)

Użycie:
    python scripts/plots/plot_july_validation.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault('MPLBACKEND', 'Agg')

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_VALIDATION = ROOT / 'data/processed/forecasts/forecast_validation.csv'
DEFAULT_OUTPUT = ROOT / 'reports/figures/july_validation_plot.png'
DEFAULT_SUMMARY = ROOT / 'reports/figures/july_validation_summary.md'
DEFAULT_DB = ROOT / 'data' / 'energy_model.db'
JULY_START = '2026-07-01'

# progi pogody (średnie cloud 6–20 z weather_data / ICON)
CLOUD_SUNNY_MAX = 40.0
CLOUD_POOR_MIN = 70.0
# różnica APE (pp) uznana za „pomaga / szkodzi”, nie szum
HYBRID_DELTA_PP = 1.0

# Pierwszy daily 5:00 z ENSEMBLE_PRIMARY=1 (gate 01.09, wdrożenie 01–02.09).
ENS_PRIMARY_START = '2026-09-02'
# ICON live: wdrożenie 17.07 ~19:52; pierwszy pełny dzień daily ≈ 18.07.
ICON_LIVE_START = '2026-07-18'
# Dual 16+CS4 + weekly obu — ostateczny stack produkcyjny (nie sam ICON).
DUAL_CALIBRATION_START = '2026-07-26'

# Tła er (start włącznie, end wyłącznie). Kolory z tej samej rodziny co ENS.
WEATHER_ERAS: list[dict] = [
    {
        'start': ICON_LIVE_START,
        'end': DUAL_CALIBRATION_START,
        'label': 'ICON',
        'color': '#1ABC9C',
    },
    {
        'start': DUAL_CALIBRATION_START,
        'end': ENS_PRIMARY_START,
        'label': 'Kalibracja dual',
        'color': '#27AE60',
    },
    {
        'start': ENS_PRIMARY_START,
        'end': None,
        'label': 'ENS primary',
        'color': '#16A085',
    },
]

# Okna closeoutów po wdrożeniu / retreningu (pierwszy dzień = pierwsza
# prognoza daily 5:00 na nowym artefakcie — patrz docs/NOTATKA_RETRENINGI_LIPIEC_2026.md).
# start/end włącznie (YYYY-MM-DD).
# Okna = zmiany logiki / targetu / cech (nie każdy niedzielny odśwież wag).
RETRAIN_SEGMENTS: list[tuple[str, str, str]] = [
    (
        '2026-07-14',
        '2026-07-18',
        'przed targetem PVE (skala mieszana; GPS/ICON 17.07)',
    ),
    (
        '2026-07-19',
        '2026-07-26',
        'po PVE 18.07 ~16:32 — przed dual 26.07',
    ),
    (
        '2026-07-27',
        '2026-09-01',
        'era dual ICON primary (po 26.07; weekly = odświeżenie wag)',
    ),
    (
        '2026-09-02',
        '2099-12-31',
        'era ENS primary (ICON+UKMO; gate 01.09, daily od 02.09)',
    ),
]

COLORS = {
    'actual': '#2C3E50',
    'raw_morning': '#2980B9',
    'hyb_morning': '#8E44AD',
    'raw_midday': '#E67E22',
    'hyb_midday': '#C0392B',
}


def load_july_validation(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Brak: {path}')

    df = pd.read_csv(path)
    if 'actual_pv_total' not in df.columns and 'actual_kwh_foxess' in df.columns:
        df['actual_pv_total'] = df['actual_kwh_foxess']

    df['target_day'] = pd.to_datetime(df['target_day'])
    if 'closeout_at' in df.columns:
        df['closeout_at'] = pd.to_datetime(df['closeout_at'])
        df = df.sort_values('closeout_at').groupby('target_day', as_index=False).last()

    df = df[df['target_day'] >= pd.Timestamp(JULY_START)].copy()

    pred_cols = (
        'actual_pv_total',
        'predicted_daily',
        'predicted_midday',
        'predicted_daily_raw',
        'predicted_midday_raw',
    )
    for col in pred_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Fallback: stare wiersze bez *_raw → traktuj operacyjną jako raw
    if 'predicted_daily_raw' not in df.columns:
        df['predicted_daily_raw'] = df.get('predicted_daily')
    else:
        df['predicted_daily_raw'] = df['predicted_daily_raw'].fillna(df['predicted_daily'])
    if 'predicted_midday_raw' not in df.columns:
        df['predicted_midday_raw'] = df.get('predicted_midday')
    else:
        df['predicted_midday_raw'] = df['predicted_midday_raw'].fillna(df['predicted_midday'])

    actual = df['actual_pv_total']
    df['err_raw_morning'] = (actual - df['predicted_daily_raw']).abs()
    df['err_hyb_morning'] = (actual - df['predicted_daily']).abs()
    df['err_raw_midday'] = (actual - df['predicted_midday_raw']).abs()
    df['err_hyb_midday'] = (actual - df['predicted_midday']).abs()

    # |APE| % = |actual − pred| / actual × 100 (dni z actual≈0 → NaN)
    denom = actual.where(actual.abs() >= 0.5)
    for src, dst in (
        ('err_raw_morning', 'ape_raw_morning'),
        ('err_hyb_morning', 'ape_hyb_morning'),
        ('err_raw_midday', 'ape_raw_midday'),
        ('err_hyb_midday', 'ape_hyb_midday'),
    ):
        df[dst] = (df[src] / denom) * 100.0

    return df.sort_values('target_day').reset_index(drop=True)


def mae(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.mean()) if not s.empty else None


def _load_daily_weather(db_path: Path, start: str) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=['day', 'cloud', 'rad', 'tmax', 'precip'])
    con = sqlite3.connect(str(db_path))
    try:
        w = pd.read_sql_query(
            """
            SELECT date(timestamp) AS day,
                   AVG(cloud_cover_percent) AS cloud,
                   AVG(solar_radiation_wm2) AS rad,
                   MAX(temperature_celsius) AS tmax,
                   SUM(COALESCE(precipitation_mm, 0)) AS precip
            FROM weather_data
            WHERE date(timestamp) >= ?
              AND CAST(strftime('%H', timestamp) AS INTEGER) BETWEEN 6 AND 20
            GROUP BY 1
            """,
            con,
            params=(start,),
        )
    finally:
        con.close()
    w['day'] = pd.to_datetime(w['day'])
    return w


def _weather_bucket(cloud: float | None) -> str:
    if cloud is None or (isinstance(cloud, float) and np.isnan(cloud)):
        return 'brak pogody'
    if cloud < CLOUD_SUNNY_MAX:
        return 'słoneczny / mało chmur'
    if cloud >= CLOUD_POOR_MIN:
        return 'pochmurny / deszczowy'
    return 'mieszany'


def build_july_error_summary(
    df: pd.DataFrame,
    *,
    db_path: Path = DEFAULT_DB,
) -> str:
    """Markdown: kiedy mniejszy/większy błąd + kiedy hybryda pomaga/szkodzi."""
    if df.empty:
        return '_Brak danych walidacji — nie da się zbudować podsumowania._\n'

    weather = _load_daily_weather(db_path, JULY_START)
    m = df.copy()
    m['day'] = pd.to_datetime(m['target_day']).dt.normalize()
    if not weather.empty:
        m = m.merge(weather, left_on='day', right_on='day', how='left')
    else:
        m['cloud'] = np.nan
        m['rad'] = np.nan
        m['tmax'] = np.nan
        m['precip'] = np.nan

    m['weather_type'] = m['cloud'].map(_weather_bucket)
    # hybryda vs raw — głównie midday (o 5:00 zwykle ≈)
    m['delta_mid_pp'] = m['ape_raw_midday'] - m['ape_hyb_midday']  # >0 → hybryda lepsza
    m['delta_morn_pp'] = m['ape_raw_morning'] - m['ape_hyb_morning']

    def _fmt_day(ts) -> str:
        return pd.Timestamp(ts).strftime('%d.%m')

    lines: list[str] = [
        '### Podsumowanie błędów (closeouty od lipca) — pogoda, hybryda, ENS',
        '',
        'Metryka: **|APE| %** = `|actual − prognoza| / actual × 100`. '
        'Pogoda: średnie **cloud 6–20** z `weather_data` (ICON; od **02.09** primary = ensemble ICON+UKMO).',
        '',
    ]

    # --- po typie pogody ---
    lines.append('#### Kiedy błąd jest mniejszy / większy')
    lines.append('')
    rows_wx = []
    for wtype, g in m.groupby('weather_type', sort=False):
        if wtype == 'brak pogody' or g.empty:
            continue
        mape5 = g['ape_raw_morning'].mean()
        mape12 = g['ape_raw_midday'].mean()
        days = ', '.join(_fmt_day(d) for d in g['target_day'])
        rows_wx.append((wtype, len(g), mape5, mape12, days))
    if rows_wx:
        lines.append('| Typ dnia (cloud) | n | MAPE raw 5:00 | MAPE raw 12:00 | Dni |')
        lines.append('|---|---:|---:|---:|---|')
        for wtype, n, mape5, mape12, days in sorted(rows_wx, key=lambda r: r[2]):
            lines.append(
                f'| {wtype} | {n} | {mape5:.1f}% | {mape12:.1f}% | {days} |'
            )
        lines.append('')

    best = m.nsmallest(3, 'ape_raw_morning')
    worst = m.nlargest(3, 'ape_raw_morning')
    lines.append(
        '- **Najtrafniejszy raw 5:00:** '
        + ', '.join(
            f"{_fmt_day(r.target_day)} ({r.ape_raw_morning:.1f}% · {r.weather_type}, "
            f"cloud~{r.cloud:.0f}%, actual {r.actual_pv_total:.1f} kWh)"
            for r in best.itertuples()
            if pd.notna(r.ape_raw_morning)
        )
    )
    lines.append(
        '- **Najgorszy raw 5:00:** '
        + ', '.join(
            f"{_fmt_day(r.target_day)} ({r.ape_raw_morning:.1f}% · {r.weather_type}, "
            f"cloud~{r.cloud:.0f}%, actual {r.actual_pv_total:.1f} kWh)"
            for r in worst.itertuples()
            if pd.notna(r.ape_raw_morning)
        )
    )
    lines.append('')
    lines.append(
        '- **Wzorzec:** na dniach **jasnych / wysokiej produkcji** raw bywa lekko **za niski** '
        '(NWP za chmurny vs Accu) — błąd umiarkowany w %, duży w kWh. '
        'Na dniach **słabych / burzowych** raw często **zawyża** — wtedy |APE| % bywa największy. '
        'Od **02.09** primary to **ENS (ICON+UKMO)** zamiast ICON solo — ten sam RF16, inna pogoda.'
    )
    lines.append('')

    # --- hybryda ---
    lines.append('#### Kiedy hybryda dnia pomaga, a kiedy szkodzi')
    lines.append('')
    lines.append(
        'Porównanie **midday (12:00)**: hybryda = FoxESS na minione godziny + RF na resztę. '
        f'„Pomaga/szkodzi” = różnica |APE| raw−hybryda ≥ **{HYBRID_DELTA_PP:.0f} pp**.'
    )
    lines.append('')

    help_m = m[m['delta_mid_pp'] >= HYBRID_DELTA_PP]
    hurt_m = m[m['delta_mid_pp'] <= -HYBRID_DELTA_PP]
    tie_m = m[m['delta_mid_pp'].abs() < HYBRID_DELTA_PP]

    def _list_days(g: pd.DataFrame) -> str:
        if g.empty:
            return '—'
        parts = []
        for r in g.sort_values('target_day').itertuples():
            sign = '↓' if r.delta_mid_pp > 0 else '↑'
            parts.append(
                f"{_fmt_day(r.target_day)} ({sign}{abs(r.delta_mid_pp):.1f} pp, {r.weather_type})"
            )
        return '; '.join(parts)

    lines.append(f'- **Hybryda pomaga (12:00):** {_list_days(help_m)}')
    lines.append(f'- **Hybryda szkodzi (12:00):** {_list_days(hurt_m)}')
    lines.append(
        f'- **Remis / szum (<{HYBRID_DELTA_PP:.0f} pp):** '
        + (', '.join(_fmt_day(d) for d in tie_m['target_day']) if len(tie_m) else '—')
    )
    lines.append('')

    # o 5:00
    help5 = int((m['delta_morn_pp'] >= HYBRID_DELTA_PP).sum())
    hurt5 = int((m['delta_morn_pp'] <= -HYBRID_DELTA_PP).sum())
    lines.append(
        f'- **O 5:00:** hybryda ≈ raw (pomaga {help5} dni / szkodzi {hurt5}) — '
        'przed wschodem prawie nie ma FoxESS do podmiany.'
    )
    lines.append('')

    # reguły narracyjne
    if len(help_m) or len(hurt_m):
        lines.append('**Reguła operacyjna (z tych closeoutów):**')
        lines.append('')
        if len(help_m):
            wx_help = help_m['weather_type'].value_counts()
            top_help = wx_help.index[0] if len(wx_help) else '—'
            lines.append(
                f'- Hybryda **najczęściej pomaga**, gdy poranek modelu był **zawyżony** '
                f'(typowo dni **słabe / pochmurne** — u nas dominanta wśród „pomaga”: **{top_help}**): '
                'FoxESS „ściąga” sumę w dół.'
            )
        if len(hurt_m):
            wx_hurt = hurt_m['weather_type'].value_counts()
            top_hurt = wx_hurt.index[0] if len(wx_hurt) else '—'
            lines.append(
                f'- Hybryda **szkodzi**, gdy raw był **za niski** na jasny dzień '
                f'(u nas dominanta wśród „szkodzi”: **{top_hurt}**), a KPI brało ścieżkę hybrydową '
                'zanim dzień się domknął — stąd reguła **outlook = model_raw** do późnego dnia.'
            )
        lines.append(
            '- **Wniosek:** hybryda godzinowa jest OK do sugestii urządzeń; '
            '**suma dnia do oceny modelu** = raw (albo hybryda dopiero wieczorem).'
        )
        lines.append('')

    # --- MAPE po retreningach ---
    lines.append('#### MAPE po retreningach / wdrożeniach')
    lines.append('')
    lines.append(
        'Podział według **zmian logiki / targetu / cech** (nie każdy niedzielny odśwież wag). '
        'Weekly retreningi wchodzą w erę dual od 27.07. '
        f'Od **{_fmt_day(ENS_PRIMARY_START)}** primary NWP = ensemble ICON+UKMO '
        '(pionowa linia / tło na wykresie). '
        'Szczegóły: `docs/NOTATKA_RETRENINGI_LIPIEC_2026.md` · gate `docs/NOTATKA_TEST_ROUTING_28-31_08.md`.'
    )
    lines.append('')
    lines.append(
        '| Okres closeoutów | Retraining / wdrożenie | n | MAPE raw 5:00 | MAPE raw 12:00 |'
    )
    lines.append('|---|---|---:|---:|---:|')
    day = pd.to_datetime(m['target_day'])
    for start, end, label in RETRAIN_SEGMENTS:
        g = m[(day >= start) & (day <= end)]
        if g.empty:
            continue
        period = f'{_fmt_day(g.target_day.min())}–{_fmt_day(g.target_day.max())}'
        lines.append(
            f'| {period} | {label} | {len(g)} | '
            f'{g["ape_raw_morning"].mean():.1f}% | {g["ape_raw_midday"].mean():.1f}% |'
        )
    pve = m[day >= '2026-07-19']
    if len(pve):
        lines.append(
            f'| {_fmt_day(pve.target_day.min())}–{_fmt_day(pve.target_day.max())} | '
            f'**era PVE łącznie** (bez 14–18) | {len(pve)} | '
            f'**{pve["ape_raw_morning"].mean():.1f}%** | '
            f'**{pve["ape_raw_midday"].mean():.1f}%** |'
        )
    lines.append('')

    n = len(m)
    mape5 = m['ape_raw_morning'].mean()
    mape12 = m['ape_raw_midday'].mean()
    lines.append(
        f'_Zakres całość: { _fmt_day(m.target_day.min()) }–{ _fmt_day(m.target_day.max()) } '
        f'({n} closeoutów) · MAPE raw 5:00 = **{mape5:.1f}%** · '
        f'MAPE raw 12:00 = **{mape12:.1f}%**._'
    )
    lines.append('')

    ens = m[day >= ENS_PRIMARY_START]
    icon_dual = m[(day >= '2026-07-27') & (day <= '2026-09-01')]
    lines.append(f'#### Notatka odświeżenia {pd.Timestamp.now().strftime("%d.%m.%Y")}')
    lines.append('')
    last = m.sort_values('target_day').tail(8)
    recent_parts = []
    for r in last.itertuples():
        if pd.notna(r.ape_raw_morning):
            recent_parts.append(
                f'{_fmt_day(r.target_day)} **{r.actual_pv_total:.1f}** '
                f'(raw 5:00 {r.ape_raw_morning:.1f}%)'
            )
        else:
            recent_parts.append(_fmt_day(r.target_day))
    recent = ', '.join(recent_parts)
    lines.append(
        f'- Zakres closeoutów: **{_fmt_day(m.target_day.min())}–{_fmt_day(m.target_day.max())}** '
        f'(n={n}). PNG + ten plik wygenerowane **{pd.Timestamp.now().strftime("%d.%m")}**.'
    )
    lines.append(
        f'- Linie na wykresie: **ICON** od **18.07** (wdrożenie 17.07 wieczór) · '
        f'**kalibracja dual** od **26.07** · **ENS primary** od **02.09**.'
    )
    lines.append(
        f'- **ENS primary** od **02.09** (gate 01.09, pierwszy daily 5:00) — '
        f'n={len(ens)} closeoutów'
        + (
            f' · MAPE raw **{ens["ape_raw_morning"].mean():.1f}% / '
            f'{ens["ape_raw_midday"].mean():.1f}%**'
            if len(ens) else ''
        )
        + '.'
    )
    if len(icon_dual):
        lines.append(
            f'- Era dual ICON **27.07–01.09** (n={len(icon_dual)}): MAPE raw '
            f'**{icon_dual["ape_raw_morning"].mean():.1f}% / '
            f'{icon_dual["ape_raw_midday"].mean():.1f}%**.'
        )
    lines.append(f'- Ostatnie closeouty (actual · |APE| raw 5:00): {recent}.')
    lines.append('')
    return '\n'.join(lines)


def _mark_weather_eras(ax, x_end=None) -> None:
    """Piony + tła: ICON (18.07) → dual/kalibracja (26.07) → ENS (02.09)."""
    right_default = x_end if x_end is not None else pd.Timestamp(ENS_PRIMARY_START) + pd.Timedelta(days=14)
    ymax = ax.get_ylim()[1]
    for i, era in enumerate(WEATHER_ERAS):
        start = pd.Timestamp(era['start'])
        end = pd.Timestamp(era['end']) if era['end'] else right_default
        if end <= start:
            continue
        ax.axvline(start, color=era['color'], linestyle='--', linewidth=1.4, alpha=0.85, zorder=0)
        ax.axvspan(start, end, color=era['color'], alpha=0.07, zorder=0)
        ax.text(
            start, ymax * (0.98 - 0.08 * (i % 2)),
            era['label'],
            rotation=90, va='top', ha='right',
            fontsize=7.5, color=era['color'], fontweight='bold', alpha=0.9,
        )


def _plot_line(ax, x, y, *, color, label, marker, linestyle='-'):
    s = pd.to_numeric(y, errors='coerce')
    mask = s.notna()
    if not mask.any():
        return
    ax.plot(
        x[mask], s[mask], marker + linestyle, color=color, linewidth=2,
        markersize=6, label=label, alpha=0.9,
    )


def build_july_plot(df: pd.DataFrame, output: Path) -> None:
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(2, 1, figsize=(13, 9.4), gridspec_kw={'height_ratios': [2, 1]})
    fig.suptitle(
        'Walidacja closeoutów — od lipca 2026 (skala PVEnergyTotal)',
        fontsize=15,
        fontweight='bold',
        y=0.995,
    )
    fig.text(
        0.5, 0.955,
        'Raw = sam RF na cały dzień  ·  Hybryda dnia = FoxESS (minione godz.) + RF (przyszłe)'
        '  ·  to nie jest korekta ADJUST',
        ha='center', va='top', fontsize=9.5, color='#34495E',
    )
    fig.text(
        0.5, 0.935,
        'Tła: ICON od 18.07 (wdrożenie 17.07 wieczór)  ·  kalibracja dual od 26.07  ·  ENS primary od 02.09',
        ha='center', va='top', fontsize=8.5, color='#16A085', style='italic',
    )

    ax1, ax2 = axes

    if df.empty:
        for ax in axes:
            ax.text(0.5, 0.5, 'Brak danych walidacji za lipiec 2026', ha='center', va='center',
                    transform=ax.transAxes)
    else:
        x = df['target_day']
        _plot_line(ax1, x, df['actual_pv_total'], color=COLORS['actual'],
                   label='Rzeczywistość (PVEnergyTotal)', marker='s')
        _plot_line(ax1, x, df['predicted_daily_raw'], color=COLORS['raw_morning'],
                   label='Raw RF 5:00 (sam model)', marker='o')
        _plot_line(ax1, x, df['predicted_daily'], color=COLORS['hyb_morning'],
                   label='Hybryda dnia 5:00 (FoxESS+RF)', marker='o', linestyle='--')
        _plot_line(ax1, x, df['predicted_midday_raw'], color=COLORS['raw_midday'],
                   label='Raw RF 12:00 (sam model)', marker='D')
        _plot_line(ax1, x, df['predicted_midday'], color=COLORS['hyb_midday'],
                   label='Hybryda dnia 12:00 (FoxESS+RF)', marker='D', linestyle='--')

        stats = []
        for label, col in (
            ('MAPE raw 5:00', 'ape_raw_morning'),
            ('MAPE hyb.dnia 5:00', 'ape_hyb_morning'),
            ('MAPE raw 12:00', 'ape_raw_midday'),
            ('MAPE hyb.dnia 12:00', 'ape_hyb_midday'),
        ):
            m = mae(df[col])
            if m is not None:
                stats.append(f'{label} = {m:.1f}%')
        if stats:
            ax1.text(
                0.02, 0.98, '  |  '.join(stats), transform=ax1.transAxes,
                va='top', fontsize=8.5,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.85),
            )

        ax1.set_title(
            'Suma dnia: o 5:00 raw≈hybryda; o 12:00 hybryda ma już poranek z falownika',
            fontsize=10, pad=8, loc='left', color='#34495E',
        )
        ax1.set_ylabel('Energia [kWh]')
        ax1.legend(loc='upper right', fontsize=8, ncol=2)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax1.tick_params(axis='x', rotation=30)
        x_end = df['target_day'].max() + pd.Timedelta(days=1)
        _mark_weather_eras(ax1, x_end)

        # |APE| %: raw vs hybryda dnia (5:00 i 12:00)
        width = 0.2
        idx = np.arange(len(df))
        pairs = (
            (idx - 1.5 * width, df['ape_raw_morning'], COLORS['raw_morning'], '|APE| raw 5:00'),
            (idx - 0.5 * width, df['ape_hyb_morning'], COLORS['hyb_morning'], '|APE| hyb.dnia 5:00'),
            (idx + 0.5 * width, df['ape_raw_midday'], COLORS['raw_midday'], '|APE| raw 12:00'),
            (idx + 1.5 * width, df['ape_hyb_midday'], COLORS['hyb_midday'], '|APE| hyb.dnia 12:00'),
        )
        for xpos, series, color, label in pairs:
            vals = series.to_numpy(dtype=float)
            mask = ~np.isnan(vals)
            if mask.any():
                ax2.bar(xpos[mask], vals[mask], width, label=label, color=color, alpha=0.85)

        ax2.set_xticks(idx)
        ax2.set_xticklabels([d.strftime('%d.%m') for d in df['target_day']], rotation=30)
        ax2.set_ylabel('|Błąd| [%]')
        ax2.set_xlabel('Dzień')
        ax2.set_title(
            '|APE| = |actual − prognoza| / actual × 100 — im później snapshot, tym więcej hybrydy to FoxESS',
            fontsize=10, pad=6, loc='left', color='#34495E',
        )
        ax2.legend(loc='upper right', fontsize=8, ncol=2)
        # Oś X = indeks dni (słupki) — linie er po numerze, nie po Timestamp.
        for era in WEATHER_ERAS:
            pos = np.flatnonzero(df['target_day'] >= pd.Timestamp(era['start']))
            if len(pos):
                ax2.axvline(
                    pos[0] - 0.5, color=era['color'],
                    linestyle='--', linewidth=1.4, alpha=0.85, zorder=0,
                )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'✓ Zapisano: {output}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Wykres walidacji lipiec 2026')
    parser.add_argument('--input', default=str(DEFAULT_VALIDATION))
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--summary', default=str(DEFAULT_SUMMARY),
                        help='Markdown podsumowania (pogoda + hybryda)')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--no-summary', action='store_true')
    args = parser.parse_args()

    df = load_july_validation(Path(args.input))
    build_july_plot(df, Path(args.output))
    print(f'   Dni w lipcu: {len(df)}')

    if not args.no_summary:
        md = build_july_error_summary(df, db_path=Path(args.db))
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(md, encoding='utf-8')
        print(f'✓ Podsumowanie: {summary_path}')
        print(md)


if __name__ == '__main__':
    main()
