#!/usr/bin/env python3
"""
Walidacja operacyjna prognoz PV — wykres dwupanelowy (od startu launchd).

Wykres 1: stabilność od 14.07 — actual vs raw RF 5:00 vs hybryda dnia 5:00
Wykres 2: ten sam zakres od 14.07 — actual + raw/hybryda dnia (5:00 i 12:00)

Terminologia:
  - raw = sam Random Forest na cały dzień
  - hybryda dnia = FoxESS (minione) + RF (przyszłe); NIE = FORECAST_OPERATIONAL_ADJUST

Źródło: data/processed/forecasts/forecast_validation.csv
Wyjście: reports/figures/production_validation_plot.png

Użycie:
    python scripts/plot_production_validation.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('MPLBACKEND', 'Agg')

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_VALIDATION = ROOT / 'data/processed/forecasts/forecast_validation.csv'
DEFAULT_OUTPUT = ROOT / 'reports/figures/production_validation_plot.png'
LONG_TERM_START = '2026-07-14'  # start archiwum midday / closeout operacyjny

COLORS = {
    'actual': '#2C3E50',
    'raw_morning': '#2980B9',
    'hyb_morning': '#8E44AD',
    'raw_midday': '#E67E22',
    'hyb_midday': '#C0392B',
    'main_raw': '#27AE60',
    'main_hyb': '#8E44AD',
}

# Retreningi i zmiany produkcji (annotacje na wykresie)
MILESTONES = [
    {'date': '2026-07-14', 'label': 'Start MLOps', 'color': '#95A5A6', 'type': 'deploy'},
    {'date': '2026-07-17', 'label': 'GPS+ICON', 'color': '#3498DB', 'type': 'deploy'},
    {'date': '2026-07-18', 'label': 'PVE target', 'color': '#9B59B6', 'type': 'deploy'},
    {'date': '2026-07-26', 'label': 'CS4 dual', 'color': '#E74C3C', 'type': 'deploy'},
    {'date': '2026-08-09', 'label': 'Retrain', 'color': '#F39C12', 'type': 'retrain'},
    {'date': '2026-08-16', 'label': 'Retrain', 'color': '#F39C12', 'type': 'retrain'},
    {'date': '2026-08-23', 'label': 'Retrain', 'color': '#F39C12', 'type': 'retrain'},
]


def load_validation_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f'Brak pliku walidacji: {path}')

    df = pd.read_csv(path)
    if df.empty:
        return df

    if 'actual_pv_total' not in df.columns and 'actual_kwh_foxess' in df.columns:
        df['actual_pv_total'] = df['actual_kwh_foxess']

    df['target_day'] = pd.to_datetime(df['target_day'])
    if 'closeout_at' in df.columns:
        df['closeout_at'] = pd.to_datetime(df['closeout_at'])
        df = df.sort_values('closeout_at').groupby('target_day', as_index=False).last()
    else:
        df = df.drop_duplicates(subset=['target_day'], keep='last')

    for col in (
        'predicted_daily',
        'predicted_midday',
        'predicted_manual',
        'predicted_daily_raw',
        'predicted_midday_raw',
        'actual_pv_total',
    ):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Stare closeouty bez *_raw → fallback na kolumnę operacyjną
    if 'predicted_daily_raw' not in df.columns:
        df['predicted_daily_raw'] = df.get('predicted_daily')
    else:
        df['predicted_daily_raw'] = df['predicted_daily_raw'].fillna(df['predicted_daily'])
    if 'predicted_midday_raw' not in df.columns:
        df['predicted_midday_raw'] = df.get('predicted_midday')
    else:
        df['predicted_midday_raw'] = df['predicted_midday_raw'].fillna(df['predicted_midday'])

    return df.sort_values('target_day').reset_index(drop=True)


def _plot_series(ax, dates, values, *, label, color, marker='o', linestyle='-', linewidth=2):
    s = pd.to_numeric(values, errors='coerce')
    mask = s.notna()
    if not mask.any():
        return
    ax.plot(
        dates[mask],
        s[mask],
        label=label,
        color=color,
        marker=marker,
        linestyle=linestyle,
        linewidth=linewidth,
        markersize=6,
        alpha=0.9,
    )


def _add_milestones(ax, zoom_start: pd.Timestamp) -> None:
    """Dodaj vertical lines z annotacjami o retreningach i deploymentach."""
    for milestone in MILESTONES:
        m_date = pd.Timestamp(milestone['date'])
        if m_date < zoom_start:
            continue  # pomiń jeśli poza zakresem
        
        ax.axvline(
            m_date, color=milestone['color'], linestyle='--',
            linewidth=1.2, alpha=0.7, zorder=0,
        )
        
        # Annotacja nad wykresem
        y_pos = 0.98 if milestone['type'] == 'retrain' else 0.92
        ax.text(
            m_date, ax.get_ylim()[1] * y_pos,
            milestone['label'],
            rotation=90, verticalalignment='top', horizontalalignment='right',
            fontsize=7.5, color=milestone['color'], alpha=0.85, fontweight='bold',
        )


def build_plot(df: pd.DataFrame, output: Path, *, long_start: str) -> None:
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10.4), sharex=False)
    fig.suptitle(
        'Walidacja PV — raw RF vs hybryda dnia (od 14.07)',
        fontsize=16,
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
        'Linie pionowe: retreningi weekly (pomarańczowe) + zmiany produkcji (kolorowe)',
        ha='center', va='top', fontsize=8.5, color='#7F8C8D', style='italic',
    )

    today = pd.Timestamp.now().normalize()
    long_df = df[df['target_day'] >= pd.Timestamp(long_start)].copy()
    # Oba panele od startu MLOps (14.07) — bez ucięcia do „ostatniej niedzieli”
    zoom_start = pd.Timestamp(long_start)
    zoom_df = long_df.copy()

    # --- Wykres 1: od startu launchd ---
    ax1.set_title(
        'Stabilność 5:00: o poranku raw ≈ hybryda dnia (mało FoxESS)',
        fontsize=12, pad=10,
    )
    if not long_df.empty:
        _plot_series(
            ax1, long_df['target_day'], long_df.get('actual_pv_total'),
            label='Rzeczywistość (PVEnergyTotal)', color=COLORS['actual'], marker='s',
        )
        _plot_series(
            ax1, long_df['target_day'], long_df.get('predicted_daily_raw'),
            label='Raw RF 5:00 (sam model)', color=COLORS['main_raw'],
        )
        _plot_series(
            ax1, long_df['target_day'], long_df.get('predicted_daily'),
            label='Hybryda dnia 5:00 (FoxESS+RF)', color=COLORS['main_hyb'], linestyle='--',
        )
    else:
        ax1.text(0.5, 0.5, 'Brak danych walidacji od 14.07', ha='center', va='center',
                 transform=ax1.transAxes, fontsize=11)

    ax1.set_ylabel('Energia [kWh]')
    ax1.legend(loc='upper left', framealpha=0.95, fontsize=9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax1.tick_params(axis='x', rotation=35)
    # Oś X od startu MLOps (bez pustego czerwca)
    x_end = max(today, long_df['target_day'].max() if not long_df.empty else today)
    ax1.set_xlim(pd.Timestamp(long_start) - pd.Timedelta(hours=12),
                 x_end + pd.Timedelta(days=1))
    
    # Dodaj annotacje retreningów i deploymentów
    _add_milestones(ax1, pd.Timestamp(long_start))

    # --- Wykres 2: zoom MLOps ---
    ax2.set_title(
        f'MLOps od {zoom_start.strftime("%d.%m.%Y")}: '
        'o 12:00 hybryda dnia ma już poranek z falownika (raw + hybryda 5:00/12:00)',
        fontsize=12,
        pad=10,
    )
    if not zoom_df.empty:
        _plot_series(
            ax2, zoom_df['target_day'], zoom_df.get('actual_pv_total'),
            label='Rzeczywistość (PVEnergyTotal)', color=COLORS['actual'], marker='s',
        )
        _plot_series(
            ax2, zoom_df['target_day'], zoom_df.get('predicted_daily_raw'),
            label='Raw RF 5:00 (sam model)', color=COLORS['raw_morning'],
        )
        _plot_series(
            ax2, zoom_df['target_day'], zoom_df.get('predicted_daily'),
            label='Hybryda dnia 5:00 (FoxESS+RF)', color=COLORS['hyb_morning'], linestyle='--',
        )
        _plot_series(
            ax2, zoom_df['target_day'], zoom_df.get('predicted_midday_raw'),
            label='Raw RF 12:00 (sam model)', color=COLORS['raw_midday'], marker='D',
        )
        _plot_series(
            ax2, zoom_df['target_day'], zoom_df.get('predicted_midday'),
            label='Hybryda dnia 12:00 (FoxESS+RF)', color=COLORS['hyb_midday'], marker='D',
            linestyle='--',
        )
    else:
        ax2.text(0.5, 0.5, 'Brak danych w oknie od 14.07', ha='center',
                 va='center', transform=ax2.transAxes, fontsize=11)

    ax2.set_xlabel('Data')
    ax2.set_ylabel('Energia [kWh]')
    ax2.legend(loc='upper left', framealpha=0.95, fontsize=9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax2.tick_params(axis='x', rotation=35)
    x_end = max(today, zoom_df['target_day'].max() if not zoom_df.empty else today)
    ax2.set_xlim(zoom_start - pd.Timedelta(hours=12), x_end + pd.Timedelta(days=1))
    
    # Dodaj annotacje retreningów i deploymentów
    _add_milestones(ax2, zoom_start)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'✓ Zapisano: {output}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Wykres walidacji operacyjnej PV')
    parser.add_argument('--input', default=str(DEFAULT_VALIDATION))
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT))
    parser.add_argument('--from', dest='date_from', default=LONG_TERM_START)
    args = parser.parse_args()

    df = load_validation_table(Path(args.input))
    if df.empty:
        print(f'⚠️  Pusty plik walidacji: {args.input}')
        print('   Uruchom evening_closeout po zebraniu danych FoxESS.')

    build_plot(df, Path(args.output), long_start=args.date_from)
    print(f'   Wierszy walidacji: {len(df)}')
    if not df.empty:
        print(f'   Zakres: {df["target_day"].min().date()} → {df["target_day"].max().date()}')


if __name__ == '__main__':
    main()
