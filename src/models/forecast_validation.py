"""Wieczorna walidacja: rzeczywista produkcja FoxESS vs zapisane prognozy."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime

import pandas as pd

from src.features.pv_features_hourly_extended import load_hourly_pv_dynamic
from src.data.foxess_pv_total import (
    get_actual_pv_total_from_report,
    get_actual_pv_total_from_timeseries,
    resolve_actual_pv_total,
)
from src.models.forecast_time import format_forecast_ts, normalize_run_at_column, parse_forecast_ts

VALIDATION_FILE = 'data/processed/forecasts/forecast_validation.csv'
HISTORY_FILE = 'data/processed/forecasts/forecast_history.csv'
HOURLY_VALIDATION_FILE = 'data/processed/forecasts/forecast_validation_hourly.csv'
PEAK_VALIDATION_FILE = 'data/processed/forecasts/forecast_validation_peak.csv'
ARCHIVE_DIR = 'data/processed/forecasts'
DEFAULT_TOP_N = 5
# Zaplanowane (cron) runy prognozy, w kolejności dnia: 05:00 / 12:00 / 16:00.
# 'manual' NIE jest tu ujęte celowo — to etykieta domyślna dla ad-hoc uruchomień
# mlops/forecast_pv.py bez --run-label (np. ręczne testy/debug), nie ma stałej pory dnia
# i bywa dużo mniej dokładna (bliżej "przypadkowego" momentu) niż zaplanowane runy.
# Pokazujemy 'manual' tylko jako fallback, gdy dla danego dnia nie ma ŻADNEGO zaplanowanego runu.
DEFAULT_RUN_LABELS = ('daily', 'midday', 'peak')
FALLBACK_RUN_LABEL = 'manual'


def get_actual_pv_ml(
    target_day: str | None = None,
    db_path: str | None = None,
) -> float:
    """Suma dzienna targetu ML = ΔPVEnergyTotal (0–23h), jak Produkcja w app."""
    target_day = target_day or date.today().isoformat()
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')

    # 0–23: suma godzin = resolve_actual_pv_total / app (nie ucinaj 5–21)
    pv = load_hourly_pv_dynamic(
        db_path, target_day, target_day, min_hour=0, max_hour=23,
    )
    if pv.empty:
        return 0.0
    return float(pv['pv_kwh_hour'].sum())


def get_actual_daily_kwh(
    target_day: str | None = None,
    db_path: str | None = None,
) -> float:
    """Alias wsteczny → get_actual_pv_ml()."""
    return get_actual_pv_ml(target_day, db_path)


def get_actual_pv_total(
    target_day: str | None = None,
    db_path: str | None = None,
) -> float | None:
    """
    PVEnergyTotal — raport API z automatycznym fallbackiem z timeseries.

    Preferuj resolve_actual_pv_total() gdy potrzebujesz źródła (report/timeseries).
    """
    kwh, _ = resolve_actual_pv_total(target_day, db_path)
    return kwh


def get_actual_hourly_ml(
    target_day: str,
    db_path: str | None = None,
) -> pd.DataFrame:
    """Godzinowa produkcja FoxESS = Δ PVEnergyTotal (timeseries), godziny 0–23."""
    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    pv = load_hourly_pv_dynamic(
        db_path, target_day, target_day, min_hour=0, max_hour=23,
    )
    if pv.empty:
        return pd.DataFrame(columns=['hour', 'actual_pv_ml_kwh'])
    out = pv[['hour', 'pv_kwh_hour']].rename(columns={'pv_kwh_hour': 'actual_pv_ml_kwh'})
    out['hour'] = out['hour'].astype(int)
    return out


def get_actual_hourly_report(
    target_day: str,
    db_path: str | None = None,
    variable: str = 'PVEnergyTotal',
) -> pd.DataFrame:
    """Godzinowa produkcja jak w app = Δ PVEnergyTotal z timeseries (0–23).

    Kolumna ``actual_report_kwh`` zachowana dla kompatybilności CSV closeout.
    Raport ``foxess_report_daily`` (generation / PVE) NIE jest źródłem —
    suma godzin z raportu bywa zaniżona vs Produkcja w app.
    Fallback do raportu tylko gdy brak timeseries.
    """
    from src.features.pv_features_hourly_extended import load_hourly_pv_from_pve

    db_path = db_path or os.getenv('DATABASE_PATH', 'data/energy_model.db')
    if not os.path.exists(db_path):
        return pd.DataFrame(columns=['hour', 'actual_report_kwh'])

    # Preferuj Δ licznika (ta sama skala co resolve_actual_pv_total / app)
    try:
        pv = load_hourly_pv_from_pve(
            db_path, target_day, target_day,
            min_hour=0, max_hour=23,
            variable=variable,
        )
    except Exception:
        pv = pd.DataFrame()

    if not pv.empty:
        out = pv[['hour', 'pv_kwh_hour']].rename(
            columns={'pv_kwh_hour': 'actual_report_kwh'}
        )
        out['hour'] = out['hour'].astype(int)
        out['actual_report_kwh'] = pd.to_numeric(out['actual_report_kwh'], errors='coerce')
        return out

    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        '''
        SELECT hour_index AS hour, value_kwh AS actual_report_kwh
        FROM foxess_report_daily
        WHERE report_date = ? AND variable = ?
        ORDER BY hour_index
        ''',
        conn,
        params=(target_day, variable),
    )
    conn.close()
    if df.empty:
        return df
    df['hour'] = df['hour'].astype(int)
    df['actual_report_kwh'] = pd.to_numeric(df['actual_report_kwh'], errors='coerce')
    return df


def _is_run_valid_for_target(run_at: pd.Timestamp, target_day: str) -> bool:
    """Odrzuca "leftover" snapshoty z ``--days 3`` (np. wczorajszy midday/peak, który
    z góry przewidział dzisiejszy dzień) gdy ``target_day`` to dziś lub przeszłość —
    wtedy wymagamy, żeby run faktycznie odbył się W tym dniu kalendarzowym (ten sam
    ``run_at.date()``), inaczej przed 12:00/16:00 pokazywalibyśmy "Południową"/
    "Popołudniową" prognozę, mimo że dzisiejszy midday/peak run jeszcze się nie odbył —
    to była wczorajsza prognoza wybiegająca 1-2 dni do przodu, błędnie brana za dzisiejszą.
    Dla dni PRZYSZŁYCH (target_day > dziś) każda prognoza z wyprzedzeniem jest legalna —
    na tym polega prognozowanie wielodniowe (--days 3)."""
    if pd.isna(run_at):
        return False
    target = pd.Timestamp(target_day).date()
    if target > date.today():
        return True
    return run_at.date() == target


def _forecast_archive_path(run_at: pd.Timestamp) -> str:
    stamp = run_at.strftime('%Y%m%d_%H%M%S')
    return os.path.join(ARCHIVE_DIR, f'pv_forecast_{stamp}.csv')


def load_forecast_snapshot(
    run_label: str,
    target_day: str,
) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Wczytaj zarchiwizowaną prognozę godzinową (daily/midday/manual)."""
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(), None

    history = pd.read_csv(HISTORY_FILE)
    sub = history[
        (history['target_day'].astype(str) == target_day)
        & (history['run_label'].astype(str) == run_label)
    ].copy()
    if sub.empty:
        return pd.DataFrame(), None

    sub['run_at'] = parse_forecast_ts(sub['run_at'])
    sub = sub[sub['run_at'].apply(lambda ts: _is_run_valid_for_target(ts, target_day))]
    if sub.empty:
        return pd.DataFrame(), None

    run_at = sub.sort_values('run_at').iloc[-1]['run_at']
    path = _forecast_archive_path(run_at)
    if not os.path.exists(path):
        return pd.DataFrame(), run_at

    fc = pd.read_csv(path)
    fc = fc[fc['day'].astype(str) == target_day].copy()
    if 'prediction_source' in fc.columns:
        fc = fc[fc['prediction_source'] == 'model']
    fc['hour'] = fc['hour'].astype(int)
    return fc, run_at


def available_forecast_labels(target_day: str) -> tuple[str, ...]:
    """Etykiety zaplanowanych runów (daily/midday/peak), dla których jest zarchiwizowana
    prognoza godzinowa. 'manual' jest dodawane tylko jako fallback, gdy nic innego nie ma
    (patrz DEFAULT_RUN_LABELS / FALLBACK_RUN_LABEL)."""
    found: list[str] = []
    for label in (*DEFAULT_RUN_LABELS, FALLBACK_RUN_LABEL):
        fc, _ = load_forecast_snapshot(label, target_day)
        if not fc.empty:
            found.append(label)
    if any(label != FALLBACK_RUN_LABEL for label in found):
        return tuple(label for label in found if label != FALLBACK_RUN_LABEL)
    return tuple(found)


def target_day_is_complete(target_day: str) -> bool:
    """Czy `target_day` ma już KOMPLETNĄ (całodniową) rzeczywistą produkcję.

    Przeszłe dni: zawsze tak. Przyszłe: zawsze nie. Dzisiejszy: dopiero po zachodzie
    słońca + margines (ta sama reguła co dynamiczne wieczorne domknięcie, patrz
    mlops/evening_closeout.py --if-after-sunset) — inaczej "Rzeczywistość" dla dziś
    to tylko produkcja DOTYCHCZASOWA (do bieżącej godziny), a porównanie jej z
    prognozą na CAŁY dzień myląco zawyża błąd (np. +107% w południe, bo dzień
    jeszcze trwa, nie dlatego że model się pomylił). Publiczna (bez `_`) — używana
    też przez `api/services/forecast_ml.py` do wystawienia dziennego pola
    `actual_so_far_kwh` niezależnie od `build_daily_forecast_summary`."""
    today = date.today()
    target = pd.Timestamp(target_day).date()
    if target < today:
        return True
    if target > today:
        return False
    try:
        from src.features.pv_features_hourly_extended import get_sunrise_sunset

        lat = float(os.getenv('WEATHER_LAT', '50.06'))
        lon = float(os.getenv('WEATHER_LON', '19.94'))
        margin = int(os.getenv('EVENING_CLOSEOUT_MARGIN_MINUTES', '30'))
        _, sunset = get_sunrise_sunset(lat, lon, target_day)
        now = datetime.now(sunset.tzinfo)
        return now >= sunset + timedelta(minutes=margin)
    except Exception:
        return False


def build_hourly_peak_validation(
    target_day: str,
    db_path: str | None = None,
    *,
    top_n: int = DEFAULT_TOP_N,
    run_labels: tuple[str, ...] | None = None,
    closeout_at: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Top-N prognozowanych godzin vs rzeczywistość FoxESS
    (ML + actual = Δ PVEnergyTotal timeseries).

    Returns:
        (tabela_top_godzin, tabela_szczytów)
    """
    closeout_at = closeout_at or format_forecast_ts(datetime.now())
    actual_ml = get_actual_hourly_ml(target_day, db_path)
    actual_report = get_actual_hourly_report(target_day, db_path)

    labels = run_labels or available_forecast_labels(target_day) or DEFAULT_RUN_LABELS

    hourly_rows: list[dict] = []
    peak_rows: list[dict] = []

    for run_label in labels:
        forecast, run_at = load_forecast_snapshot(run_label, target_day)
        if forecast.empty:
            continue

        top = forecast.nlargest(top_n, 'predicted_kwh').reset_index(drop=True)
        pred_peak = forecast.loc[forecast['predicted_kwh'].idxmax()]

        actual_peak_ml = None
        actual_peak_report = None
        if not actual_ml.empty:
            actual_peak_ml = actual_ml.loc[actual_ml['actual_pv_ml_kwh'].idxmax()]
        if not actual_report.empty:
            actual_peak_report = actual_report.loc[actual_report['actual_report_kwh'].idxmax()]

        peak_rows.append({
            'closeout_at': closeout_at,
            'target_day': target_day,
            'run_label': run_label,
            'forecast_run_at': format_forecast_ts(run_at) if run_at is not None else None,
            'predicted_peak_hour': int(pred_peak['hour']),
            'predicted_peak_kwh': round(float(pred_peak['predicted_kwh']), 3),
            'actual_peak_hour_ml': (
                int(actual_peak_ml['hour']) if actual_peak_ml is not None else None
            ),
            'actual_peak_kwh_ml': (
                round(float(actual_peak_ml['actual_pv_ml_kwh']), 3)
                if actual_peak_ml is not None else None
            ),
            'actual_peak_hour_report': (
                int(actual_peak_report['hour']) if actual_peak_report is not None else None
            ),
            'actual_peak_kwh_report': (
                round(float(actual_peak_report['actual_report_kwh']), 3)
                if actual_peak_report is not None else None
            ),
            'peak_hour_error_ml': (
                int(pred_peak['hour']) - int(actual_peak_ml['hour'])
                if actual_peak_ml is not None else None
            ),
            'peak_hour_error_report': (
                int(pred_peak['hour']) - int(actual_peak_report['hour'])
                if actual_peak_report is not None else None
            ),
        })

        for rank, row in enumerate(top.itertuples(index=False), start=1):
            hour = int(row.hour)
            pred_kwh = float(row.predicted_kwh)

            ml_row = actual_ml[actual_ml['hour'] == hour]
            rep_row = actual_report[actual_report['hour'] == hour]
            actual_ml_kwh = float(ml_row.iloc[0]['actual_pv_ml_kwh']) if not ml_row.empty else None
            actual_rep_kwh = float(rep_row.iloc[0]['actual_report_kwh']) if not rep_row.empty else None

            hourly_rows.append({
                'closeout_at': closeout_at,
                'target_day': target_day,
                'run_label': run_label,
                'forecast_run_at': format_forecast_ts(run_at) if run_at is not None else None,
                'rank': rank,
                'predicted_hour': hour,
                'predicted_kwh': round(pred_kwh, 3),
                'actual_pv_ml_kwh': round(actual_ml_kwh, 3) if actual_ml_kwh is not None else None,
                'actual_report_kwh': round(actual_rep_kwh, 3) if actual_rep_kwh is not None else None,
                'error_vs_ml_kwh': (
                    round(pred_kwh - actual_ml_kwh, 3) if actual_ml_kwh is not None else None
                ),
                'error_vs_ml_pct': (
                    round((pred_kwh - actual_ml_kwh) / actual_ml_kwh * 100, 1)
                    if actual_ml_kwh not in (None, 0) else None
                ),
                'error_vs_report_kwh': (
                    round(pred_kwh - actual_rep_kwh, 3) if actual_rep_kwh is not None else None
                ),
                'is_actual_peak_ml': (
                    actual_peak_ml is not None and hour == int(actual_peak_ml['hour'])
                ),
                'is_actual_peak_report': (
                    actual_peak_report is not None and hour == int(actual_peak_report['hour'])
                ),
            })

    return pd.DataFrame(hourly_rows), pd.DataFrame(peak_rows)


def build_daily_forecast_summary(
    target_day: str,
    db_path: str | None = None,
    *,
    run_labels: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Suma dobowa: prognoza (per run_label) vs rzeczywista produkcja, z błędem w kWh i %.

    Źródło prognozy: kolumna ``predicted_kwh`` z forecast_history.csv (ta sama wartość
    operacyjna, której używa record_evening_closeout()) — NIE suma archiwum godzinowego
    (load_forecast_snapshot). Dla runów zrobionych w trakcie dnia (midday/peak/manual)
    archiwum godzinowe zawiera tylko godziny JESZCZE DO PRZEWIDZENIA — przeszłe godziny
    mają tam ``prediction_source='foxess_actual'`` i są odfiltrowane przez
    load_forecast_snapshot, więc zsumowanie samych wierszy 'model' sztucznie zaniżałoby
    prognozę całego dnia (np. midday 12:00 pokazywałby tylko prognozę na 12-24, a nie
    actual-so-far + model, jak w oficjalnym forecast_history.csv).

    Konwencja znaku: error_kwh = predicted − actual (dodatni = model przeszacował),
    spójna z error_vs_ml_kwh w build_hourly_peak_validation.

    Dopóki dzień TRWA (patrz `target_day_is_complete`), "rzeczywistość" to tylko
    produkcja DOTYCHCZASOWA (do bieżącej godziny) — porównanie jej z prognozą na
    CAŁY dzień myląco zawyżałoby błąd (np. w południe prognoza na 24h vs produkcja
    z pół dnia = pozorne "+100%"). W tym wypadku `actual_total_kwh` / `error_kwh` /
    `error_pct` = None — pojawiają się DOPIERO po zamknięciu dnia (po zachodzie
    słońca + margines, czyli po wieczornej synchronizacji, patrz T1.17). Widok
    "produkcji dotychczas" w trakcie dnia jest osobnym, jednorazowym polem na
    poziomie całej odpowiedzi (`actual_so_far_kwh` w `get_forecast_validation()`),
    a nie per run_label tutaj — patrz `api/services/forecast_ml.py`.
    """
    actual_total = get_actual_pv_ml(target_day, db_path)
    has_actual = actual_total is not None and actual_total > 0
    is_complete = target_day_is_complete(target_day)

    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame()

    history = pd.read_csv(HISTORY_FILE)
    sub = history[history['target_day'].astype(str) == target_day].copy()
    if sub.empty:
        return pd.DataFrame()
    sub['run_at'] = parse_forecast_ts(sub['run_at'])
    sub = sub[sub['run_at'].apply(lambda ts: _is_run_valid_for_target(ts, target_day))]
    if sub.empty:
        return pd.DataFrame()

    available = set(sub['run_label'].astype(str).unique())
    scheduled = tuple(l for l in DEFAULT_RUN_LABELS if l in available)
    labels = run_labels or scheduled or tuple(l for l in (FALLBACK_RUN_LABEL,) if l in available)

    rows: list[dict] = []
    for run_label in labels:
        group = sub[sub['run_label'].astype(str) == run_label]
        if group.empty:
            continue
        row = group.sort_values('run_at').iloc[-1]
        if pd.isna(row.get('predicted_kwh')):
            continue

        predicted_total = _day_outlook_from_history_row(row)
        run_at = row['run_at']
        outlook_mode = None
        if 'outlook_mode' in row.index and pd.notna(row.get('outlook_mode')):
            outlook_mode = str(row['outlook_mode'])
        elif (
            'predicted_kwh_raw' in row.index
            and pd.notna(row.get('predicted_kwh_raw'))
            and float(row['predicted_kwh_raw']) - float(row['predicted_kwh']) > 0.5
            and float(row.get('actual_kwh_in_forecast') or 0) > 0
        ):
            outlook_mode = 'model_raw'  # wstecznie: hybryda zaniżyła sumę (np. midday 28/29.07)

        if is_complete:
            error_kwh = (predicted_total - actual_total) if has_actual else None
            error_pct = (error_kwh / actual_total * 100) if error_kwh is not None else None
            actual_total_display = actual_total if has_actual else None
        else:
            error_kwh = None
            error_pct = None
            actual_total_display = None

        rows.append({
            'run_label': run_label,
            'forecast_run_at': format_forecast_ts(run_at) if pd.notna(run_at) else None,
            'predicted_total_kwh': round(predicted_total, 2),
            'outlook_mode': outlook_mode,
            'actual_total_kwh': round(actual_total_display, 2) if actual_total_display is not None else None,
            'error_kwh': round(error_kwh, 2) if error_kwh is not None else None,
            'error_pct': round(error_pct, 1) if error_pct is not None else None,
        })

    return pd.DataFrame(rows)


def _day_outlook_from_history_row(row: pd.Series) -> float:
    """Suma dnia do kart UI: outlook (raw w południe), nie ścieżka hybrydowa.

    Nowe archiwa mają już ``predicted_kwh`` = outlook + ``outlook_mode``.
    Stare midday/peak: gdy FoxESS podmienił rano i suma hybrydy < raw → bierz raw.
    """
    pred = float(row['predicted_kwh'])
    if 'outlook_mode' in row.index and pd.notna(row.get('outlook_mode')):
        return pred
    raw = None
    if 'predicted_kwh_raw' in row.index and pd.notna(row.get('predicted_kwh_raw')):
        raw = float(row['predicted_kwh_raw'])
    actual_in = float(row['actual_kwh_in_forecast']) if pd.notna(row.get('actual_kwh_in_forecast')) else 0.0
    if raw is not None and actual_in > 0 and pred < raw - 0.5:
        return raw
    return pred


def save_hourly_peak_validation(
    target_day: str,
    db_path: str | None = None,
    *,
    top_n: int = DEFAULT_TOP_N,
    run_labels: tuple[str, ...] | None = None,
    closeout_at: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Zbuduj i zapisz tabele walidacji godzinowej (nadpisuje wiersze dla target_day)."""
    hourly_df, peak_df = build_hourly_peak_validation(
        target_day,
        db_path,
        top_n=top_n,
        run_labels=run_labels,
        closeout_at=closeout_at,
    )
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    for path, df in (
        (HOURLY_VALIDATION_FILE, hourly_df),
        (PEAK_VALIDATION_FILE, peak_df),
    ):
        if df.empty:
            continue
        if os.path.exists(path):
            prev = pd.read_csv(path)
            prev = prev[prev['target_day'].astype(str) != target_day]
            df = pd.concat([prev, df], ignore_index=True)
        df.to_csv(path, index=False)

    return hourly_df, peak_df


def _latest_predictions_by_label(history: pd.DataFrame, target_day: str) -> dict[str, float]:
    """Ostatni snapshot per etykieta — wartość operacyjna (po korekcie / predicted_kwh)."""
    detail = _latest_prediction_detail_by_label(history, target_day)
    return {label: vals['adjusted'] for label, vals in detail.items() if vals.get('adjusted') is not None}


def _latest_prediction_detail_by_label(
    history: pd.DataFrame,
    target_day: str,
) -> dict[str, dict[str, float | None]]:
    """Ostatni snapshot per etykieta: raw + adjusted (gdy brak raw → = adjusted)."""
    sub = history[history['target_day'].astype(str) == target_day].copy()
    if sub.empty:
        return {}
    sub['run_at'] = parse_forecast_ts(sub['run_at'])
    sub = sub[sub['run_at'].apply(lambda ts: _is_run_valid_for_target(ts, target_day))]
    if sub.empty:
        return {}
    out: dict[str, dict[str, float | None]] = {}
    for label, group in sub.groupby('run_label'):
        row = group.sort_values('run_at').iloc[-1]
        adjusted = float(row['predicted_kwh']) if pd.notna(row.get('predicted_kwh')) else None
        raw = None
        if 'predicted_kwh_raw' in row.index and pd.notna(row.get('predicted_kwh_raw')):
            raw = float(row['predicted_kwh_raw'])
        elif 'predicted_kwh_adjusted' in row.index and pd.notna(row.get('predicted_kwh_adjusted')):
            # starsze wiersze: tylko predicted_kwh (= adjusted)
            raw = adjusted
        else:
            raw = adjusted
        out[str(label)] = {'raw': raw, 'adjusted': adjusted}
    return out


def backfill_history_snapshots(target_day: str, snapshots: dict[str, float]) -> None:
    """Dopisz brakujące snapshoty prognozy (np. z logów, gdy archiwum nie było włączone)."""
    if not snapshots:
        return
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        history = pd.read_csv(HISTORY_FILE)
    else:
        history = pd.DataFrame(columns=[
            'run_at', 'run_label', 'target_day', 'predicted_kwh',
            'actual_kwh_in_forecast', 'peak_hour', 'peak_kwh',
        ])

    existing = set(
        zip(
            history[history['target_day'].astype(str) == target_day]['run_label'].astype(str),
            history[history['target_day'].astype(str) == target_day]['target_day'].astype(str),
        )
    ) if not history.empty else set()

    rows = []
    for label, predicted in snapshots.items():
        if (label, target_day) in existing:
            continue
        rows.append({
            'run_at': format_forecast_ts(datetime.now()),
            'run_label': label,
            'target_day': target_day,
            'predicted_kwh': round(float(predicted), 2),
            'actual_kwh_in_forecast': None,
            'peak_hour': None,
            'peak_kwh': None,
        })
    if rows:
        history = pd.concat([history, pd.DataFrame(rows)], ignore_index=True)
        history = normalize_run_at_column(history, 'run_at')
        history.to_csv(HISTORY_FILE, index=False)


def record_evening_closeout(
    target_day: str | None = None,
    db_path: str | None = None,
    actual_kwh_override: float | None = None,
) -> dict:
    """
    Porównaj rzeczywistą produkcję z ostatnimi prognozami (daily/midday/manual).
    Dopisuje wiersz do forecast_validation.csv.

    actual_pv_total  — PVEnergyTotal (raport API → fallback timeseries hybrid)
    actual_pv_source — report | timeseries | override | none
    actual_pv_ml     — target modelu (domyślnie ΔPVEnergyTotal, jak app)
    """
    target_day = target_day or date.today().isoformat()
    closeout_at = format_forecast_ts(datetime.now())

    actual_ml = get_actual_pv_ml(target_day, db_path)
    actual_total, actual_source = resolve_actual_pv_total(
        target_day,
        db_path,
        actual_kwh_override=actual_kwh_override,
        pv_power_daily_kwh=actual_ml if actual_ml > 0 else None,
    )

    report_only = get_actual_pv_total_from_report(target_day, db_path)
    ts_only = get_actual_pv_total_from_timeseries(target_day, db_path)

    # Błędy prognoz względem PVEnergyTotal (raport → timeseries → pvPower)
    ref_actual = actual_total if actual_total is not None and actual_total > 0 else actual_ml

    preds_detail: dict[str, dict[str, float | None]] = {}
    if os.path.exists(HISTORY_FILE):
        history = pd.read_csv(HISTORY_FILE)
        preds_detail = _latest_prediction_detail_by_label(history, target_day)

    def _adj(label: str) -> float | None:
        d = preds_detail.get(label) or {}
        return d.get('adjusted')

    def _raw(label: str) -> float | None:
        d = preds_detail.get(label) or {}
        return d.get('raw')

    predicted_daily = _adj('daily')
    predicted_midday = _adj('midday')
    predicted_manual = _adj('manual')
    predicted_daily_raw = _raw('daily')
    predicted_midday_raw = _raw('midday')
    predicted_manual_raw = _raw('manual')
    # Dual CS4 (produkcja równoległa)
    predicted_daily_cs4 = _adj('daily_cs4')
    predicted_midday_cs4 = _adj('midday_cs4')
    predicted_peak_cs4 = _adj('peak_cs4')
    if predicted_daily_cs4 is None:
        predicted_daily_cs4 = _raw('daily_cs4')
    if predicted_midday_cs4 is None:
        predicted_midday_cs4 = _raw('midday_cs4')
    if predicted_peak_cs4 is None:
        predicted_peak_cs4 = _raw('peak_cs4')

    # ICON solo shadow (gdy ENSEMBLE_PRIMARY — daily = ens, daily_icon = ICON)
    predicted_daily_icon = _adj('daily_icon')
    predicted_midday_icon = _adj('midday_icon')
    predicted_peak_icon = _adj('peak_icon')
    if predicted_daily_icon is None:
        predicted_daily_icon = _raw('daily_icon')
    if predicted_midday_icon is None:
        predicted_midday_icon = _raw('midday_icon')
    if predicted_peak_icon is None:
        predicted_peak_icon = _raw('peak_icon')

    candidates = {
        k: v['adjusted'] for k, v in preds_detail.items()
        if k != 'evening' and v.get('adjusted') is not None
    }
    best_label = None
    best_pred = None
    best_error = None
    if candidates and ref_actual > 0:
        best_label = min(candidates, key=lambda k: abs(candidates[k] - ref_actual))
        best_pred = candidates[best_label]
        best_error = ref_actual - best_pred

    # Best vs surowy RF (osobno — do oceny modelu bez korekty)
    candidates_raw = {
        k: v['raw'] for k, v in preds_detail.items()
        if k != 'evening' and v.get('raw') is not None
    }
    best_raw_label = None
    best_raw_pred = None
    best_raw_error = None
    if candidates_raw and ref_actual > 0:
        best_raw_label = min(candidates_raw, key=lambda k: abs(candidates_raw[k] - ref_actual))
        best_raw_pred = candidates_raw[best_raw_label]
        best_raw_error = ref_actual - best_raw_pred

    ref_pred = predicted_midday if predicted_midday is not None else predicted_daily
    error_kwh = (ref_actual - ref_pred) if ref_pred is not None else None
    error_pct = (error_kwh / ref_actual * 100) if error_kwh is not None and ref_actual > 0 else None

    row = {
        'closeout_at': closeout_at,
        'target_day': target_day,
        'actual_pv_total': round(actual_total, 2) if actual_total is not None else None,
        'actual_pv_source': actual_source,
        'actual_pv_report': round(report_only, 2) if report_only is not None else None,
        'actual_pv_timeseries': round(ts_only, 2) if ts_only is not None else None,
        'actual_pv_ml': round(actual_ml, 2) if actual_ml > 0 else None,
        'predicted_daily': round(predicted_daily, 2) if predicted_daily is not None else None,
        'predicted_daily_raw': round(predicted_daily_raw, 2) if predicted_daily_raw is not None else None,
        'predicted_midday': round(predicted_midday, 2) if predicted_midday is not None else None,
        'predicted_midday_raw': round(predicted_midday_raw, 2) if predicted_midday_raw is not None else None,
        'predicted_manual': round(predicted_manual, 2) if predicted_manual is not None else None,
        'predicted_manual_raw': round(predicted_manual_raw, 2) if predicted_manual_raw is not None else None,
        'error_vs_midday_kwh': (
            round(ref_actual - predicted_midday, 2) if predicted_midday is not None else None
        ),
        'error_vs_daily_kwh': (
            round(ref_actual - predicted_daily, 2) if predicted_daily is not None else None
        ),
        'error_vs_daily_raw_kwh': (
            round(ref_actual - predicted_daily_raw, 2) if predicted_daily_raw is not None else None
        ),
        'error_vs_midday_raw_kwh': (
            round(ref_actual - predicted_midday_raw, 2) if predicted_midday_raw is not None else None
        ),
        'predicted_daily_cs4': (
            round(predicted_daily_cs4, 2) if predicted_daily_cs4 is not None else None
        ),
        'predicted_midday_cs4': (
            round(predicted_midday_cs4, 2) if predicted_midday_cs4 is not None else None
        ),
        'predicted_peak_cs4': (
            round(predicted_peak_cs4, 2) if predicted_peak_cs4 is not None else None
        ),
        'error_vs_daily_cs4_kwh': (
            round(ref_actual - predicted_daily_cs4, 2) if predicted_daily_cs4 is not None else None
        ),
        'error_vs_midday_cs4_kwh': (
            round(ref_actual - predicted_midday_cs4, 2) if predicted_midday_cs4 is not None else None
        ),
        'predicted_daily_icon': (
            round(predicted_daily_icon, 2) if predicted_daily_icon is not None else None
        ),
        'predicted_midday_icon': (
            round(predicted_midday_icon, 2) if predicted_midday_icon is not None else None
        ),
        'predicted_peak_icon': (
            round(predicted_peak_icon, 2) if predicted_peak_icon is not None else None
        ),
        'error_vs_daily_icon_kwh': (
            round(ref_actual - predicted_daily_icon, 2) if predicted_daily_icon is not None else None
        ),
        'error_vs_midday_icon_kwh': (
            round(ref_actual - predicted_midday_icon, 2) if predicted_midday_icon is not None else None
        ),
        'error_vs_reference_kwh': round(error_kwh, 2) if error_kwh is not None else None,
        'error_vs_reference_pct': round(error_pct, 1) if error_pct is not None else None,
        'best_snapshot_label': best_label,
        'best_snapshot_kwh': round(best_pred, 2) if best_pred is not None else None,
        'best_snapshot_error_kwh': round(best_error, 2) if best_error is not None else None,
        'best_snapshot_raw_label': best_raw_label,
        'best_snapshot_raw_kwh': round(best_raw_pred, 2) if best_raw_pred is not None else None,
        'best_snapshot_raw_error_kwh': round(best_raw_error, 2) if best_raw_error is not None else None,
    }

    os.makedirs(os.path.dirname(VALIDATION_FILE), exist_ok=True)
    df = pd.DataFrame([row])
    if os.path.exists(VALIDATION_FILE):
        prev = pd.read_csv(VALIDATION_FILE)
        prev = prev[prev['target_day'].astype(str) != target_day]
        df = pd.concat([prev, df], ignore_index=True)
    df.to_csv(VALIDATION_FILE, index=False)

    hourly_df, peak_df = save_hourly_peak_validation(
        target_day,
        db_path,
        closeout_at=closeout_at,
    )
    row['hourly_validation_rows'] = len(hourly_df)
    row['peak_validation_rows'] = len(peak_df)

    return row
