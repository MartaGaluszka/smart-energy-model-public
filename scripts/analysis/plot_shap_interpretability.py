#!/usr/bin/env python
"""
SHAP — interpretowalność modelu produkcyjnego RF (16 cech).

Generuje:
  - summary plot (beeswarm + bar) z podpisami
  - waterfall (pojedyncza prognoza — godzina szczytu PV)
  - dependence plot (radiation_wm2, cloud_cover_pct)
  - force plot HTML
  - reports/shap_interpretation.md — komentarze do wykresów

Uruchomienie (z katalogu projektu):
    python scripts/analysis/plot_shap_interpretability.py
    python scripts/analysis/plot_shap_interpretability.py --max-samples 300
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))
_db = os.getenv('DATABASE_PATH', 'data/energy_model.db')
if not os.path.isabs(_db):
    os.environ['DATABASE_PATH'] = os.path.join(ROOT, _db)

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split

from src.features.pv_features_hourly_extended import (
    HOURLY_FEATURE_COLUMNS_PRODUCTION,
    TARGET_COLUMN,
    load_hourly_training_frame_extended,
)
from src.models.pv_hourly_predictor import DEFAULT_MODEL_PATH, PVHourlyPredictor

TRAIN_START = '2025-06-01'
TRAIN_END = '2026-05-31'
FIG_DIR = os.path.join(ROOT, 'reports', 'figures')
DOCS_ML_DIR = os.path.join(ROOT, 'docs', 'images', 'ml')
REPORT_MD = os.path.join(ROOT, 'reports', 'shap_interpretation.md')

FEATURE_LABELS = {
    'hour': 'Godzina',
    'temp_c': 'Temperatura [°C]',
    'humidity_pct': 'Wilgotność [%]',
    'cloud_cover_pct': 'Zachmurzenie [%]',
    'radiation_wm2': 'Radiacja [W/m²]',
    'wind_speed_ms': 'Wiatr [m/s]',
    'sunrise_hour': 'Wschód [h]',
    'sunset_hour': 'Zachód [h]',
    'day_length_hours': 'Długość dnia [h]',
    'hours_since_sunrise': 'Od wschodu [h]',
    'hours_until_sunset': 'Do zachodu [h]',
    'sun_position': 'Pozycja słońca',
    'is_daylight': 'Jest dzień',
    'snow_on_panels': 'Śnieg na panelach',
    'snow_on_panels_prev': 'Śnieg (poprzedni dzień)',
    'likely_fog_day': 'Mgła (dzień)',
}

PLOT_COMMENTS = {
    'ranking': {
        'title': 'Ranking cech — mean |SHAP|',
        'caption': 'Średni bezwzględny wpływ każdej cechy na prognozę godzinową [kWh/h].',
        'body': (
            'Tabela sortuje cechy po **mean |SHAP|** — im wyżej, tym częściej i silniej dana zmienna '
            'przesuwa prognozę RF. Na szczycie listy są **zachmurzenie** i **geometria dnia** '
            '(`hours_until_sunset`, `sun_position`), a nie surowa **godzina kalendarzowa** (`hour` '
            'jest dopiero ~9. pozycji). To uzasadnia ablację 19→16 cech: model opiera się na fizyce '
            'PV i NWP, nie na sztywnym „o 12:00 zawsze X kWh".'
        ),
    },
    'bar': {
        'title': 'Summary bar — średni wpływ cech',
        'caption': 'Długość słupka = mean |SHAP| · RF produkcyjny · holdout 20% dni · tylko is_daylight=1.',
        'body': (
            'Wykres słupkowy to **zagregowany** obraz ważności: ile średnio każda cecha „rusza" '
            'prognozą we wszystkich godzinach testowych. **Zachmurzenie** ma największy udział — '
            'zgodnie z intuicją (pochmurny dzień → mniej kWh). **Do zachodu** i **pozycja słońca** '
            'kodują kształt profilu dobowego (rano vs południe vs wieczór). **Radiacja** jest '
            '4. na liście — ważna, ale częściowo skorelowana z chmurami i kątem słońca.'
        ),
    },
    'beeswarm': {
        'title': 'Summary beeswarm — kierunek i rozkład wpływu',
        'caption': 'Oś X: SHAP [kWh/h] · kolor: wartość cechy · każdy punkt = jedna godzina testowa.',
        'body': (
            'Każda kropka to **jedna godzina** ze zbioru testowego. Pozycja w poziomie: **SHAP > 0** '
            'podnosi prognozę względem średniej modelu, **SHAP < 0** ją obniża. Kolor pokazuje '
            'wartość cechy (np. czerwone = wysokie zachmurzenie). Widać, że przy **dużym '
            'zachmurzeniu** punkty idą w lewo (ujemny wpływ), a przy **wysokiej radiacji** — '
            'w prawo. Rozproszenie w pionie przy tej samej cechie oznacza **interakcje** z innymi '
            'zmiennymi (RF jest nieliniowy).'
        ),
    },
    'dependence_radiation_wm2': {
        'title': 'Dependence — radiacja [W/m²]',
        'caption': 'Oś Y: wpływ radiacji na prognozę · oś X: radiacja · kolor: interakcja z inną cechą.',
        'body': (
            'Pokazuje, jak ** sama wartość radiacji** przekłada się na korektę prognozy. Przy '
            'niskiej radiacji (<200 W/m²) wpływ jest bliski zera — model „wie", że i tak mało '
            'wyprodukujesz. Powyżej ~400 W/m² SHAP rośnie dodatnio: silne słońce podbija kWh/h. '
            'Kolor punktów sugeruje, że ten sam poziom radiacji może działać inaczej w zależności '
            'np. od chmur lub pory dnia.'
        ),
    },
    'dependence_cloud_cover_pct': {
        'title': 'Dependence — zachmurzenie [%]',
        'caption': 'Przy wysokim cloud_cover SHAP schodzi w minus — mniej energii niż przy czystym niebie.',
        'body': (
            'Najczytelniejsza monotonia: **im więcej chmur, tym niższa prognoza**. To potwierdza, '
            'że model nie ignoruje pogody na rzecz samego kalendarza — kluczowe dla dni burzowych '
            '(błąd operacyjny 21.07 w analizie błędów). Szeroki „garb" przy średnim zachmurzeniu '
            'to godziny, gdzie inne cechy (radiacja, pozycja słońca) modulują efekt chmur.'
        ),
    },
    'waterfall': {
        'title': 'Waterfall — skład prognozy w godzinie szczytu PV',
        'caption': 'f(x) = E[f(X)] + Σ SHAP — przykład z najwyższą rzeczywistą PV w próbce testowej.',
        'body': (
            'Waterfall rozkłada **jedną konkretną prognozę** na sumę wpływów: start od **wartości '
            'bazowej** modelu (średnia), potem kolejne cechy dokładają lub odejmują kWh/h. '
            'Wybrano godzinę z **maksymalną rzeczywistą produkcją** w próbce — widać, '
            'które cechy „dociągnęły" prognozę w górę (słońce, radiacja) i co ją hamowało '
            '(chmury). Odpowiednik **force plot** w wersji statycznej pod slajd / PDF.'
        ),
    },
    'force_html': {
        'title': 'Force plot (HTML) — ten sam przykład interaktywnie',
        'caption': 'Czerwone = podbija prognozę · niebieskie = obniża · otwórz plik HTML w przeglądarce.',
        'body': (
            'Interaktywny **force plot** dla tej samej godziny co waterfall. Przydatny na obronie '
            'live (przewijanie, zoom). Plik: `reports/figures/shap_force_peak_hour.html`.'
        ),
    },
}


def _load_test_frame(max_samples: int) -> tuple[pd.DataFrame, pd.Series]:
    df = load_hourly_training_frame_extended(start_date=TRAIN_START, end_date=TRAIN_END)
    days = df['day'].unique()
    _, test_days = train_test_split(days, test_size=0.2, random_state=42)
    test = df[df['day'].isin(test_days)].copy()
    if 'is_daylight' in test.columns:
        test = test[test['is_daylight'] == 1]
    if len(test) > max_samples:
        test = test.sample(n=max_samples, random_state=42)
    X = test[HOURLY_FEATURE_COLUMNS_PRODUCTION]
    y = test[TARGET_COLUMN]
    return X, y


def _display_names(columns: list[str]) -> list[str]:
    return [FEATURE_LABELS.get(c, c) for c in columns]


def _caption_figure(title: str, caption: str) -> None:
    fig = plt.gcf()
    fig.suptitle(title, fontsize=11, fontweight='bold', y=1.02)
    fig.text(
        0.5, 0.01, caption,
        ha='center', va='bottom', fontsize=8.5, color='#444444',
        wrap=True, transform=fig.transFigure,
    )
    fig.subplots_adjust(bottom=0.14, top=0.90)


def _write_interpretation_md(ranking: pd.DataFrame, peak_pv_kwh: float, n_samples: int) -> str:
    lines = [
        '# SHAP — komentarze do wykresów',
        '',
        f'*Model: Random Forest produkcyjny (16 cech) · próbka testowa: {n_samples} godzin dziennych · '
        f'przykład peak PV: {peak_pv_kwh:.2f} kWh/h*',
        '',
        '---',
        '',
    ]
    order = [
        'ranking', 'bar', 'beeswarm',
        'dependence_radiation_wm2', 'dependence_cloud_cover_pct',
        'waterfall', 'force_html',
    ]
    for key in order:
        block = PLOT_COMMENTS[key]
        lines.append(f"## {block['title']}")
        lines.append('')
        lines.append(f"*{block['caption']}*")
        lines.append('')
        lines.append(block['body'])
        lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## Top 10 cech (mean |SHAP|)')
    lines.append('')
    lines.append('| # | Cecha | mean \\|SHAP\\| |')
    lines.append('|---|-------|-------------|')
    for n, (_, row) in enumerate(ranking.head(10).iterrows(), 1):
        lines.append(f"| {n} | {row['label']} | {row['mean_abs_shap']:.4f} |")
    lines.append('')
    text = '\n'.join(lines) + '\n'
    os.makedirs(os.path.dirname(REPORT_MD), exist_ok=True)
    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.write(text)
    return REPORT_MD


def run(max_samples: int = 400, model_path: str = DEFAULT_MODEL_PATH) -> dict[str, str]:
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(DOCS_ML_DIR, exist_ok=True)

    predictor = PVHourlyPredictor(model_path=model_path)
    predictor.load()
    pipeline = predictor.pipeline
    imputer = pipeline.named_steps['imputer']
    rf = pipeline.named_steps['model']

    X_test, y_test = _load_test_frame(max_samples)
    X_imp = pd.DataFrame(
        imputer.transform(X_test),
        columns=HOURLY_FEATURE_COLUMNS_PRODUCTION,
        index=X_test.index,
    )
    display = _display_names(HOURLY_FEATURE_COLUMNS_PRODUCTION)

    print(f'Obliczanie SHAP dla {len(X_imp)} wierszy testowych (RF, 16 cech)...')
    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_imp)

    outputs: dict[str, str] = {}
    comments = PLOT_COMMENTS

    # 1) Summary beeswarm
    plt.figure(figsize=(10, 7.5))
    shap.summary_plot(
        shap_values, X_imp, feature_names=display, show=False, max_display=16,
    )
    _caption_figure(comments['beeswarm']['title'], comments['beeswarm']['caption'])
    path_beeswarm = os.path.join(FIG_DIR, 'shap_summary_beeswarm.png')
    plt.savefig(path_beeswarm, dpi=150, bbox_inches='tight')
    plt.close()
    outputs['beeswarm'] = path_beeswarm
    print(f'  ✓ {path_beeswarm}')

    # 2) Summary bar
    plt.figure(figsize=(9, 6.5))
    shap.summary_plot(
        shap_values, X_imp, feature_names=display, plot_type='bar', show=False, max_display=16,
    )
    _caption_figure(comments['bar']['title'], comments['bar']['caption'])
    path_bar = os.path.join(FIG_DIR, 'shap_summary_bar.png')
    plt.savefig(path_bar, dpi=150, bbox_inches='tight')
    plt.close()
    outputs['bar'] = path_bar
    print(f'  ✓ {path_bar}')

    # 3) Dependence
    for feat, key in (
        ('radiation_wm2', 'dependence_radiation_wm2'),
        ('cloud_cover_pct', 'dependence_cloud_cover_pct'),
    ):
        idx = HOURLY_FEATURE_COLUMNS_PRODUCTION.index(feat)
        plt.figure(figsize=(7, 5.5))
        shap.dependence_plot(idx, shap_values, X_imp, feature_names=display, show=False)
        _caption_figure(comments[key]['title'], comments[key]['caption'])
        path_dep = os.path.join(FIG_DIR, f'shap_dependence_{feat}.png')
        plt.savefig(path_dep, dpi=150, bbox_inches='tight')
        plt.close()
        outputs[key] = path_dep
        print(f'  ✓ {path_dep}')

    # 4) Waterfall
    peak_idx = y_test.idxmax()
    peak_pv = float(y_test.loc[peak_idx])
    local_pos = X_imp.index.get_loc(peak_idx)
    explanation = shap.Explanation(
        values=shap_values[local_pos],
        base_values=explainer.expected_value,
        data=X_imp.iloc[local_pos].values,
        feature_names=display,
    )
    plt.figure(figsize=(10, 6.5))
    shap.plots.waterfall(explanation, show=False, max_display=12)
    _caption_figure(comments['waterfall']['title'], comments['waterfall']['caption'])
    path_waterfall = os.path.join(FIG_DIR, 'shap_waterfall_peak_hour.png')
    plt.savefig(path_waterfall, dpi=150, bbox_inches='tight')
    plt.close()
    outputs['waterfall'] = path_waterfall
    print(f'  ✓ {path_waterfall} (peak PV={peak_pv:.2f} kWh/h)')

    # 5) Force plot HTML
    force_path = os.path.join(FIG_DIR, 'shap_force_peak_hour.html')
    force = shap.force_plot(
        explainer.expected_value,
        shap_values[local_pos],
        X_imp.iloc[local_pos],
        feature_names=display,
        matplotlib=False,
        show=False,
    )
    shap.save_html(force_path, force)
    outputs['force_html'] = force_path
    print(f'  ✓ {force_path}')

    for src in outputs.values():
        if src.endswith('.png'):
            dst = os.path.join(DOCS_ML_DIR, os.path.basename(src))
            with open(src, 'rb') as fin, open(dst, 'wb') as fout:
                fout.write(fin.read())

    mean_abs = np.abs(shap_values).mean(axis=0)
    ranking = pd.DataFrame({
        'feature': HOURLY_FEATURE_COLUMNS_PRODUCTION,
        'label': display,
        'mean_abs_shap': mean_abs,
    }).sort_values('mean_abs_shap', ascending=False)
    csv_path = os.path.join(ROOT, 'data', 'processed', 'shap_feature_ranking.csv')
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    ranking.to_csv(csv_path, index=False)
    outputs['ranking_csv'] = csv_path
    print(f'  ✓ {csv_path}')

    md_path = _write_interpretation_md(ranking, peak_pv, len(X_imp))
    outputs['interpretation_md'] = md_path
    print(f'  ✓ {md_path}')

    print('\nTop 5 cech (mean |SHAP|):')
    for _, row in ranking.head(5).iterrows():
        print(f"  {row['label']:28s} {row['mean_abs_shap']:.4f}")

    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description='SHAP interpretowalność RF produkcyjny')
    parser.add_argument('--max-samples', type=int, default=400, help='Maks. wierszy testowych')
    parser.add_argument('--model-path', default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    print('=' * 60)
    print('SHAP — Random Forest 16 cech (produkcja)')
    print('=' * 60)
    run(max_samples=args.max_samples, model_path=args.model_path)
    print('\nGotowe.')


if __name__ == '__main__':
    main()
