"""
Smart Energy — dashboard operacyjny (MVP).

Uruchomienie z katalogu projektu:
    source venv/bin/activate
    streamlit run dashboard/app.py

Zakres MVP:
  1) formularz → weather_notes
  2) lista notatek
  3) prognoza RF vs app (forecast_validation)
  4) wpis faktury Tauron → tauron_bills (+ opcjonalnie tariff / meter_readings)
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime

import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

from src.data.tauron_invoices import (  # noqa: E402
    DOC_TYPES,
    TauronInvoiceInput,
    build_bill_number,
    build_pdf_path_metadata,
    list_bills,
    load_deposit_ledger,
    load_forecast_vs_bills,
    period_exists,
    save_invoice,
    suggested_next_period,
    tariff_defaults,
)
from src.financial.prosumer_deposit import (  # noqa: E402
    load_deposit_rcem_report,
    load_rcem_vs_hourly_comparison,
)
from src.data.weather_notes import (  # noqa: E402
    NOTE_KINDS,
    SOURCES,
    insert_note,
    list_notes,
    load_forecast_validation,
    validation_summary,
)

st.set_page_config(
    page_title='Smart Energy — dashboard',
    page_icon='☀️',
    layout='wide',
)

st.title('Smart Energy — panel operacyjny')
st.caption(
    'RF godzinowy · ICON · target PVE · notatki pogodowe i rachunki Tauron (nie wchodzą do modelu PV)'
)


def _render_deposit_rcem_tab(*, show_chart: bool = True) -> None:
    """RCEm × oddanie vs faktury Tauron (poz. 4–6)."""
    st.markdown(
        '**Model rozliczeniowy Tauron:** należny depozyt = **oddanie [kWh] × RCEm** miesiąca eksportu. '
        'Orientacyjnie trafia na fakturę **+2 miesiące**. Poz. 5 = **saldo do odliczenia** '
        '(jesienią 2025 zużywasz zgromadzony depozyt z lata).'
    )

    try:
        report = load_deposit_rcem_report(os.path.join(ROOT, 'data', 'energy_model.db'))
    except Exception as exc:
        st.error(f'Nie udało się policzyć depozytu RCEm: {exc}')
        return

    summary = report['summary']
    accrual = report['accrual']
    invoices = report['invoices']
    pending = report.get('pending', pd.DataFrame())

    st.markdown('#### Suma do odebrania z Tauron')
    st.metric(
        'Σ do odliczenia (RCEm − użyte na fakturach)',
        f"{summary['suma_do_odebrania_zl']:.2f} zł",
        help='Łączna wartość depozytu wg RCEm×oddanie, której Tauron jeszcze nie odliczył w poz. 5',
    )
    d1, d2, d3 = st.columns(3)
    d1.metric(
        'w drodze (czeka na fakturę docelową)',
        f"{summary.get('depozyt_w_drodze_zl', 0):.2f} zł",
        help='Część łącznej kwoty do odliczenia — należne za eksport VI–VII trafi na faktury VIII–IX',
    )
    d2.metric(
        'saldo depozytu (pula, po ostatniej fakturze)',
        f"{summary['saldo_model_koncowe_zl']:.2f} zł",
        help='Σ należne RCEm (eksport do tego mc) − Σ użyte poz. 5; nie schodzi poniżej zera',
    )
    d3.metric(
        'ostatnia faktura w bazie',
        summary.get('ostatnia_faktura_miesiac') or '—',
    )
    if not pending.empty:
        show_pend = pending.copy()
        for col in ['oddanie_kwh', 'rcem_zl_mwh', 'nalezny_depozyt_zl']:
            if col in show_pend.columns:
                show_pend[col] = show_pend[col].round(2)
        st.caption('Należne za eksport — orientacyjna faktura docelowa (+2 mc):')
        st.dataframe(show_pend, use_container_width=True, hide_index=True)
    else:
        st.caption('Brak eksportów oczekujących na przyszłą fakturę.')

    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Σ należne RCEm × oddanie', f"{summary['suma_nalezny_rcem_zl']:.2f} zł")
    c2.metric('Σ użyte na fakturach (poz. 5)', f"{summary['suma_uzyty_faktury_zl']:.2f} zł")
    c3.metric('Saldo depozytu (pula)', f"{summary['saldo_model_koncowe_zl']:.2f} zł")
    c4.metric('Opóźnienie depozytu', f"{summary['delay_months']} mc")

    st.markdown('**1. Należny depozyt za miesiąc eksportu** (oddanie × RCEm miesięczna PSE — nie RCE godzinowa)')
    if accrual.empty:
        st.info('Brak danych eksportu / RCEm.')
    else:
        show_acc = accrual.copy()
        for col in ['oddanie_kwh', 'rcem_zl_mwh', 'nalezny_depozyt_zl']:
            if col in show_acc.columns:
                show_acc[col] = show_acc[col].round(2)
        cols = [
            c for c in [
                'miesiac_eksportu', 'oddanie_kwh', 'rcem_zl_mwh', 'nalezny_depozyt_zl',
                'faktura_docelowa', 'rcem_zrodlo',
            ] if c in show_acc.columns
        ]
        st.dataframe(show_acc[cols], use_container_width=True, hide_index=True)
        computed = accrual[accrual.get('rcem_zrodlo', pd.Series(dtype=str)) == 'computed_from_rce']
        if not computed.empty:
            months = ', '.join(computed['miesiac_eksportu'].astype(str).tolist())
            st.caption(
                f'Wstępna RCEm (średnia kwadransów) dla: **{months}** — po publikacji PSE '
                'uzupełnij `data/rcem_pse_seed.json` i uruchom `fetch_rcem.py --import-seed`.'
            )

    st.markdown('**2. Faktura vs model** — depozyt użyty (poz. 5) vs należne z eksportów M−2')
    if not invoices.empty:
        show_inv = invoices.copy()
        for col in [
            'depozyt_uzyty_faktura_zl',
            'nalezne_rcem_2mc_zl',
            'roznica_uzyty_minus_nalezne',
            'saldo_model_przed_zl',
            'saldo_model_po_zl',
        ]:
            if col in show_inv.columns:
                show_inv[col] = show_inv[col].round(2)
        st.dataframe(show_inv, use_container_width=True, hide_index=True)

        jesien = invoices[invoices['faktura_za_miesiac'].isin(['2025-10', '2025-11', '2025-12'])]
        if not jesien.empty:
            st.info(
                '**Jesień 2025:** duże poz. 5 (115 / 352 / 92 zł) to **zużycie zgromadzonego depozytu** '
                'z letnich eksportów (VIII–IX), nie tylko RCEm za jeden miesiąc. '
                'Wykres salda pokazuje **pulę depozytu** (należne od początku − użyte); nie schodzi poniżej zera.'
            )

        if show_chart:
            chart_df = invoices.dropna(subset=['depozyt_uzyty_faktura_zl']).copy()
            if not chart_df.empty:
                st.markdown('**Depozyt użyty na fakturze (poz. 5)**')
                st.line_chart(
                    chart_df.set_index('faktura_za_miesiac')[['depozyt_uzyty_faktura_zl', 'nalezne_rcem_2mc_zl']]
                )
                st.markdown('**Saldo depozytu (pula po fakturze)**')
                st.line_chart(chart_df.set_index('faktura_za_miesiac')[['saldo_model_po_zl']])

    st.markdown('**3. Wpisy z faktur PDF** (poz. 4–6 — surowe metadane)')
    dep = load_deposit_ledger()
    if dep.empty:
        st.caption('Brak metadanych depozytu w fakturach.')
    else:
        show_dep = dep.copy()
        for col in [
            'depozyt_okres_zl', 'depozyt_poprzednie_zl', 'rozliczenie_depozytu_zl',
            'wynik_brutto_zl', 'do_zaplaty_zl', 'oddanie_kwh',
        ]:
            if col in show_dep.columns:
                show_dep[col] = show_dep[col].round(2)
        st.dataframe(
            show_dep[
                [c for c in [
                    'okres', 'depozyt_okres_zl', 'depozyt_poprzednie_zl',
                    'rozliczenie_depozytu_zl', 'do_zaplaty_zl', 'oddanie_kwh',
                ] if c in show_dep.columns]
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_deposit_rcem_vs_hourly_tab(*, show_chart: bool = True) -> None:
    """Porównanie: stawka miesięczna RCEm vs RCE godzinowa PSE."""
    st.info(
        '**To nie jest saldo u Tauron** — scenariusz „co gdyby” dla tych samych miesięcy. '
        'Obie metody dają kwoty **dodatnie**; minus przy różnicy znaczy tylko **„o tyle mniej/więcej”** '
        'niż przy RCEm, a nie dług wobec sprzedawcy.'
    )
    st.markdown(
        '**RCEm** = oddanie z **faktury** × stawka miesięczna PSE (tak rozlicza Tauron). '
        '**RCE godz.** = eksport z **FoxESS/licznika** × cena z każdej godziny PSE.'
    )

    try:
        cmp_report = load_rcem_vs_hourly_comparison(os.path.join(ROOT, 'data', 'energy_model.db'))
    except Exception as exc:
        st.error(f'Nie udało się porównać RCEm vs RCE godzinowa: {exc}')
        return

    cmp_df = cmp_report['comparison']
    cmp_sum = cmp_report['summary']

    if cmp_df.empty:
        st.info('Brak miesięcy z eksportem do porównania.')
        return

    okres_od = cmp_sum.get('okres_wspolny_od')
    okres_do = cmp_sum.get('okres_wspolny_do')
    if okres_od and okres_do:
        st.markdown(f'#### Porównanie wspólnego okresu: **{okres_od} – {okres_do}**')
        w1, w2, w3 = st.columns(3)
        w1.metric(
            'RCEm (oddanie z faktury)',
            f"{cmp_sum.get('suma_rcem_wspolne_mc_zl', 0):.2f} zł",
        )
        w2.metric(
            'RCE godz. brutto (FoxESS)',
            f"{cmp_sum.get('suma_rce_godz_brutto_wspolne_zl', 0):.2f} zł",
        )
        mniej = cmp_sum.get('godzinowka_mniej_niz_rcem_zl')
        wiecej = cmp_sum.get('godzinowka_wiecej_niz_rcem_zl')
        if mniej is not None:
            w3.metric(
                'Przy godzinówce',
                f'{mniej:.2f} zł mniej',
                help='O tyle mniej dostałbyś przy rozliczeniu godzinowym brutto vs RCEm',
            )
        elif wiecej is not None:
            w3.metric(
                'Przy godzinówce',
                f'{wiecej:.2f} zł więcej',
                help='O tyle więcej dostałbyś przy rozliczeniu godzinowym brutto vs RCEm',
            )
        else:
            w3.metric('Przy godzinówce', '—')

    st.markdown('#### Sumy całości (różne okresy — nie porównywać 1:1)')
    c1, c2 = st.columns(2)
    c1.metric(
        f"Σ RCEm — wszystkie faktury ({cmp_sum['miesiecy_rcem']} mc)",
        f"{cmp_sum['suma_rcem_zl']:.2f} zł",
    )
    c2.metric(
        f"Σ RCE godz. — tylko mc z FoxESS ({cmp_sum['miesiecy_godzinowa']} mc)",
        f"{cmp_sum['suma_rce_godz_brutto_zl']:.2f} zł",
        help='2025 bez kwadransów RCE w bazie — brak kolumny godzinowej',
    )

    both_df = cmp_df[
        cmp_df['depozyt_rce_godz_brutto_zl'].notna() & cmp_df['depozyt_rcem_zl'].notna()
    ].copy()
    if not both_df.empty:
        st.markdown('**Tabela — tylko miesiące z oboma metodami**')
        show_cmp = both_df.copy()
        show_cmp['roznica_opis'] = show_cmp['roznica_godz_brutto_minus_rcem_zl'].apply(
            lambda x: (
                f'{abs(x):.2f} zł mniej przy godz.'
                if pd.notna(x) and x < 0
                else (
                    f'{x:.2f} zł więcej przy godz.'
                    if pd.notna(x) and x > 0
                    else '0 zł'
                )
            )
        )
        rename = {
            'miesiac': 'Miesiąc',
            'oddanie_faktura_kwh': 'Oddanie faktura [kWh]',
            'oddanie_godzinowe_kwh': 'Oddanie FoxESS [kWh]',
            'rcem_zl_mwh': 'RCEm [zł/MWh]',
            'depozyt_rcem_zl': 'Wartość RCEm [zł]',
            'depozyt_rce_godz_brutto_zl': 'RCE godz. brutto [zł]',
            'depozyt_rce_godz_netto_zl': 'RCE godz. netto [zł]',
            'roznica_opis': 'Różnica (godz. vs RCEm)',
        }
        cols = [c for c in rename if c in show_cmp.columns]
        for col in show_cmp.select_dtypes(include='number').columns:
            show_cmp[col] = show_cmp[col].round(2)
        st.dataframe(
            show_cmp[cols].rename(columns=rename),
            use_container_width=True,
            hide_index=True,
        )

    only_rcem = cmp_df[cmp_df['depozyt_rce_godz_brutto_zl'].isna() & cmp_df['depozyt_rcem_zl'].notna()]
    if not only_rcem.empty:
        with st.expander(
            f'Pozostałe miesiące — tylko RCEm ({len(only_rcem)} mc, brak RCE godzinowej w bazie)',
            expanded=False,
        ):
            st.dataframe(
                only_rcem[['miesiac', 'oddanie_faktura_kwh', 'depozyt_rcem_zl', 'uwagi']]
                .rename(columns={
                    'miesiac': 'Miesiąc',
                    'oddanie_faktura_kwh': 'Oddanie [kWh]',
                    'depozyt_rcem_zl': 'RCEm [zł]',
                    'uwagi': 'Uwagi',
                })
                .round(2),
                use_container_width=True,
                hide_index=True,
            )

    st.caption(
        'RCE godz. netto = Σ max(0, eksport_h − import_h) × RCE_h. '
        'Ujemna wartość brutto (np. IV 2026) = eksport w godzinach z ujemną ceną RCE — nadal scenariusz, nie faktura.'
    )

    if show_chart and not both_df.empty:
        chart_df = both_df.copy()
        st.line_chart(
            chart_df.set_index('miesiac')[['depozyt_rcem_zl', 'depozyt_rce_godz_brutto_zl']]
            .rename(columns={
                'depozyt_rcem_zl': 'RCEm [zł]',
                'depozyt_rce_godz_brutto_zl': 'RCE godz. brutto [zł]',
            })
        )


def render_deposit_panel(*, show_chart: bool = True) -> None:
    """Kalkulator depozytu: RCEm (Tauron) + porównanie z RCE godzinową."""
    tab_rcem, tab_vs_hourly = st.tabs(['RCEm × oddanie (Tauron)', 'RCEm vs RCE godzinowa'])
    with tab_rcem:
        _render_deposit_rcem_tab(show_chart=show_chart)
    with tab_vs_hourly:
        _render_deposit_rcem_vs_hourly_tab(show_chart=show_chart)


tab_notes, tab_forecast, tab_tauron, tab_deposit, tab_about = st.tabs(
    ['Notatki pogodowe', 'Prognoza vs app', 'Rachunki Tauron', 'Depozyt prosumencki', 'O panelu']
)

with tab_notes:
    st.subheader('Wpisz obserwację / Accu / Meteoblue')
    with st.form('weather_note_form', clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            note_day = st.date_input('Dzień którego dotyczy', value=date.today())
            source = st.selectbox('Źródło', SOURCES)
            note_kind = st.selectbox('Rodzaj', NOTE_KINDS, index=0)
        with c2:
            cloud = st.number_input('Zachmurzenie %', min_value=0.0, max_value=100.0, value=None, placeholder='np. 71')
            uv = st.number_input('UV', min_value=0.0, max_value=15.0, value=None, placeholder='np. 7')
            brightness = st.number_input('Brightness / AccuLumen', min_value=0.0, max_value=10.0, value=None)
            precip_mm = st.number_input('Opady mm', min_value=0.0, value=None, placeholder='np. 3.4')
        with c3:
            precip_prob = st.number_input('P opadów %', min_value=0.0, max_value=100.0, value=None)
            wind_dir = st.text_input('Kierunek wiatru', placeholder='np. SW')
            wind_kmh = st.number_input('Wiatr km/h', min_value=0.0, value=None)
            wind_gust = st.number_input('Porywy km/h', min_value=0.0, value=None)

        note_text = st.text_area(
            'Opis ( Accu / MB / własna obserwacja )',
            placeholder='np. ~14:20 zanik słońca, intensywny deszcz',
            height=100,
        )
        recorded_date = st.date_input('Data wpisu', value=date.today(), key='rec_day')
        recorded_time = st.time_input('Godzina wpisu', value=datetime.now().time().replace(second=0, microsecond=0))

        submitted = st.form_submit_button('Zapisz do weather_notes', type='primary')

    if submitted:
        if not note_text or not str(note_text).strip():
            st.error('Dodaj krótki opis w polu tekstowym.')
        else:
            recorded_at = datetime.combine(recorded_date, recorded_time).replace(microsecond=0).isoformat()
            try:
                row_id = insert_note(
                    note_day=note_day.isoformat(),
                    source=source,
                    note_kind=note_kind,
                    recorded_at=recorded_at,
                    cloud_cover_pct=cloud,
                    uv_index=uv,
                    brightness_index=brightness,
                    wind_dir=wind_dir or None,
                    wind_kmh=wind_kmh,
                    wind_gust_kmh=wind_gust,
                    precip_prob_pct=precip_prob,
                    precip_mm=precip_mm,
                    rain_mm=precip_mm,
                    note_text=str(note_text).strip(),
                )
                st.success(f'Zapisano notatkę id={row_id} na dzień {note_day.isoformat()}')
            except Exception as exc:
                st.error(f'Nie udało się zapisać: {exc}')

    st.subheader('Ostatnie notatki')
    limit = st.slider('Ile wierszy', 5, 50, 20)
    notes = list_notes(limit=limit)
    if notes.empty:
        st.info('Brak notatek w bazie.')
    else:
        show_cols = [
            c
            for c in [
                'id',
                'note_day',
                'recorded_at',
                'source',
                'note_kind',
                'cloud_cover_pct',
                'uv_index',
                'precip_mm',
                'precip_prob_pct',
                'note_text',
            ]
            if c in notes.columns
        ]
        st.dataframe(notes[show_cols], use_container_width=True, hide_index=True)

with tab_tauron:
    st.subheader('Wpis faktury / rozliczenia Tauron')
    st.caption(
        'Koszty energii i dystrybucji = **netto** · razem = **brutto** (jak na fakturze). '
        'Ten sam okres rozliczeniowy **nadpisze** poprzedni wpis (korekta).'
    )

    td = tariff_defaults()
    if td.get('valid_from'):
        st.info(f'Stawki G12w w formularzu: auto z ostatniego wpisu tauron_tariff (**ważne od {td["valid_from"]}**).')
    else:
        st.info('Brak tauron_tariff w bazie — stawki domyślne (szablon G12w).')

    tariff_from_default = date.fromisoformat(td['valid_from']) if td.get('valid_from') else date.today().replace(day=1)
    default_period_start, default_period_end = suggested_next_period()
    st.caption(
        f'Sugerowany okres do wpisu: **{default_period_start.isoformat()} → {default_period_end.isoformat()}** '
        '(następny miesiąc po ostatniej fakturze w bazie).'
    )

    with st.expander(
        'Jak przepisać z faktury/PDF — formularz (przykład: lipiec 2026)',
        expanded=False,
    ):
        st.markdown(
            '''
| Na fakturze / w app | Pole w formularzu | Lipiec 2026 |
|---|---|---|
| Licznik **pobór** szczyt / pozaszczyt | Strefa T1 / T2 | **6** + **16** = 22 kWh |
| Licznik **oddanie** szczyt / pozaszczyt | Oddanie T1 / T2 (i łącznie) | **204** + **203** = 407 kWh |
| **Razem za sprzedaż** → *wartość netto* | **Energia netto** | **36,02 zł** |
| **Razem za dystrybucję** → *wartość netto* | **Dystrybucja netto** | **43,23 zł** |
| Akcyza (stopka PDF) | **Akcyza / stałe** | **0,49 zł** |
| **3. Wynik rozliczenia** → *wartość brutto* | **Razem brutto** | **97,48 zł** |
| **5. Depozyt z okresów poprzednich** | Depozyt poprzednie | **12,80 zł** |
| **Razem (3−6)** | Do zapłaty po depozycie | **84,68 zł** |
| Termin płatności | Termin płatności | **20.08.2026** |

**Z app (skrót):** poz. 1–2 mają też kolumnę *wartość netto* — wpisuj **netto**, nie brutto.
Brutto (44,30 / 53,18) służy tylko do kontroli; **Razem brutto** bierz z poz. 3 (**97,48 zł**), nie z „Do zapłaty”.

**Sierpień:** okres **2026-08-01 → 2026-08-31**, te same pola — licznik i „Razem za sprzedaż/dystrybucję” z PDF.
            '''
        )

    with st.form('tauron_invoice_form', clear_on_submit=False):
        h1, h2, h3 = st.columns(3)
        with h1:
            doc_type = st.selectbox('Rodzaj dokumentu', DOC_TYPES)
            period_start = st.date_input('Okres od', value=default_period_start)
            period_end = st.date_input('Okres do', value=default_period_end)
        with h2:
            bill_date = st.date_input('Data faktury / rozliczenia', value=date.today())
            invoice_number = st.text_input('Numer faktury', placeholder='np. T/K1/BC389/0006/26')
            issue_date = st.date_input('Data wystawienia', value=date.today())
        with h3:
            payment_deadline = st.date_input('Termin płatności', value=date.today())
            deposit_period = st.number_input('Depozyt okres [zł] (poz. 4 PDF)', min_value=0.0, value=0.0, step=0.01)
            deposit_previous = st.number_input('Depozyt poprzednie [zł] (poz. 5 PDF)', min_value=0.0, value=0.0, step=0.01)
            amount_due = st.number_input('Do zapłaty po depozycie [zł brutto]', min_value=0.0, value=0.0, step=0.01)

        st.markdown('**Pobór (G12w)**')
        p1, p2, p3 = st.columns(3)
        with p1:
            zone1 = st.number_input('Strefa szczyt (T1) [kWh]', min_value=0.0, value=0.0, step=0.1)
        with p2:
            zone2 = st.number_input('Strefa pozaszczyt (T2) [kWh]', min_value=0.0, value=0.0, step=0.1)
        with p3:
            st.metric('Pobór łącznie [kWh]', f'{(zone1 + zone2):.1f}')

        st.markdown('**Oddanie do sieci**')
        e1, e2, e3 = st.columns(3)
        with e1:
            export_total = st.number_input('Oddanie łącznie [kWh]', min_value=0.0, value=0.0, step=0.1)
        with e2:
            export_z1 = st.number_input('Oddanie szczyt [kWh]', min_value=0.0, value=0.0, step=0.1)
        with e3:
            export_z2 = st.number_input('Oddanie pozaszczyt [kWh]', min_value=0.0, value=0.0, step=0.1)

        st.markdown('**Koszty (z faktury)**')
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            energy_net = st.number_input('Energia netto [zł]', min_value=0.0, value=0.0, step=0.01)
        with c2:
            distrib_net = st.number_input('Dystrybucja netto [zł]', min_value=0.0, value=0.0, step=0.01)
        with c3:
            fixed_costs = st.number_input('Akcyza / stałe [zł]', min_value=0.0, value=0.0, step=0.01)
        with c4:
            total_brutto = st.number_input('Razem brutto [zł]', min_value=0.0, value=0.0, step=0.01)

        export_value = st.number_input(
            'Wartość oddanej energii po RCE [zł] (opcjonalnie)',
            min_value=0.0,
            value=0.0,
            step=0.01,
            help='Net-billing — można uzupełnić później skryptem calculate_prosumer_deposit.py',
        )

        save_meter = st.checkbox('Zapisz też do meter_readings (odczyt licznika)', value=True)
        save_tariff = st.checkbox('Zapisz stawki do tauron_tariff', value=False)

        if save_tariff:
            st.markdown('**Stawki G12w (przy zapisie tariff)**')
            t1, t2, t3 = st.columns(3)
            with t1:
                tariff_from = st.date_input('Ważne od', value=tariff_from_default, key='tariff_from')
                price_z1 = st.number_input(
                    'Cena szczyt netto [zł/kWh]', min_value=0.0,
                    value=float(td['price_zone1_day']), step=0.0001, format='%.4f',
                )
                price_z2 = st.number_input(
                    'Cena pozaszczyt netto [zł/kWh]', min_value=0.0,
                    value=float(td['price_zone2_night']), step=0.0001, format='%.4f',
                )
            with t2:
                dist_z1 = st.number_input(
                    'Dystrybucja szczyt netto [zł/kWh]', min_value=0.0,
                    value=float(td['distribution_zone1']), step=0.0001, format='%.4f',
                )
                dist_z2 = st.number_input(
                    'Dystrybucja pozaszczyt netto [zł/kWh]', min_value=0.0,
                    value=float(td['distribution_zone2']), step=0.0001, format='%.4f',
                )
                sub_fee = st.number_input(
                    'Opłaty stałe mies. [zł]', min_value=0.0,
                    value=float(td['subscription_fee_monthly']), step=0.01,
                )
            with t3:
                power_fee = st.number_input(
                    'Opłata mocowa mies. [zł]', min_value=0.0,
                    value=float(td['power_fee_monthly']), step=0.01,
                )
                oze_fee = st.number_input(
                    'Opłata OZE [zł/kWh]', min_value=0.0,
                    value=float(td['oze_fee_kwh']), step=0.0001, format='%.4f',
                )
                cog_fee = st.number_input(
                    'Opłata kogeneracyjna [zł/kWh]', min_value=0.0,
                    value=float(td['cogenerative_fee_kwh']), step=0.0001, format='%.4f',
                )
            tariff_notes = st.text_input(
                'Notatka do stawek',
                value=td.get('tariff_notes') or '',
                placeholder='np. cennik z faktury maj 2026',
            )

        tauron_submit = st.form_submit_button('Zapisz rachunek Tauron', type='primary')

    ps = period_start.isoformat()
    pe = period_end.isoformat()
    if period_exists(ps, pe):
        st.warning(f'Okres **{ps} → {pe}** jest już w bazie — zapis **nadpisze** istniejący rachunek.')

    if tauron_submit:
        if total_brutto <= 0:
            st.error('Podaj kwotę brutto (razem do zapłaty z faktury).')
        elif period_start > period_end:
            st.error('Data początku okresu musi być wcześniejsza niż koniec.')
        else:
            bill_no = build_bill_number(doc_type, ps, pe, invoice_number or None)
            meta = build_pdf_path_metadata(
                doc_type=doc_type,
                period_start=ps,
                period_end=pe,
                invoice_number=invoice_number or None,
                issue_date=issue_date.isoformat(),
                payment_deadline=payment_deadline.isoformat(),
                deposit_period=deposit_period if deposit_period > 0 else 0.0,
                deposit_previous=deposit_previous if deposit_previous > 0 else None,
                amount_due=amount_due if amount_due > 0 else None,
            )
            payload = TauronInvoiceInput(
                billing_period_start=ps,
                billing_period_end=pe,
                bill_date=bill_date.isoformat(),
                bill_number=bill_no,
                actual_zone1_kwh=zone1,
                actual_zone2_kwh=zone2,
                actual_energy_cost=energy_net,
                actual_distribution_cost=distrib_net,
                actual_fixed_costs=fixed_costs,
                actual_total_cost=total_brutto,
                energy_exported_kwh=export_total,
                energy_exported_value=export_value if export_value > 0 else None,
                export_zone1_kwh=export_z1 if export_z1 > 0 else None,
                export_zone2_kwh=export_z2 if export_z2 > 0 else None,
                pdf_path=meta,
                save_meter_reading=save_meter,
                save_tariff=save_tariff,
                tariff_valid_from=tariff_from.isoformat() if save_tariff else None,
                price_zone1_day=price_z1 if save_tariff else None,
                price_zone2_night=price_z2 if save_tariff else None,
                distribution_zone1=dist_z1 if save_tariff else None,
                distribution_zone2=dist_z2 if save_tariff else None,
                subscription_fee_monthly=sub_fee if save_tariff else None,
                power_fee_monthly=power_fee if save_tariff else None,
                oze_fee_kwh=oze_fee if save_tariff else None,
                cogenerative_fee_kwh=cog_fee if save_tariff else None,
                tariff_notes=tariff_notes or None,
            )
            try:
                result = save_invoice(payload)
                st.success(
                    f'Zapisano **{result["bill_number"]}** · okres {result["period"]} · '
                    f'pobór {result["import_kwh"]:.1f} kWh · oddanie {result["export_kwh"]:.1f} kWh · '
                    f'brutto {result["total_brutto"]:.2f} zł'
                )
            except Exception as exc:
                st.error(f'Nie udało się zapisać: {exc}')

    st.subheader('Ostatnie rachunki')
    bill_limit = st.slider('Ile wierszy', 5, 36, 12, key='bill_limit')
    bills = list_bills(limit=bill_limit)
    if bills.empty:
        st.info('Brak rachunków w tauron_bills — wpisz pierwszą fakturę powyżej.')
    else:
        st.dataframe(bills, use_container_width=True, hide_index=True)

    st.subheader('Prognoza vs faktura (blankiety Tauron)')
    st.caption(
        'Blankiet ~2 miesiące vs **suma** faktur w tym okresie (po 1 wpisie na miesiąc). '
        '**Koszt** = energia netto (jak w app) · **Pobór kWh** = osobna metryka (u prosumenta bywa dużo wyższy od prognozy zużycia).'
    )
    fv = load_forecast_vs_bills()
    if fv.empty:
        st.info('Brak par prognoza+faktura — uzupełnij `tauron_forecast` (blankiety) i `tauron_bills`.')
    else:
        complete_energy = fv.dropna(subset=['faktura_energia_zl', 'prognoza_energia_zl'])
        c1, c2, c3 = st.columns(3)
        c1.metric('Blankiety w bazie', len(fv))
        if not complete_energy.empty:
            c2.metric(
                'Śr. Δ energia netto',
                f"{complete_energy['delta_energia_zl'].mean():+.0f} zł",
            )
            c3.metric(
                'Śr. Δ pobór (info)',
                f"{fv['delta_kwh'].dropna().mean():+.0f} kWh",
            )
        else:
            c2.metric('Śr. Δ energia netto', '—')
            c3.metric('Śr. Δ pobór (info)', '—')

        show_fv = fv.copy()
        round_cols = [
            'prognoza_kwh', 'faktura_kwh', 'delta_kwh',
            'prognoza_energia_zl', 'faktura_energia_zl', 'delta_energia_zl',
            'prognoza_brutto_zl', 'faktura_brutto_zl', 'delta_brutto_zl',
            'prognoza_do_zaplaty_zl', 'faktura_do_zaplaty_zl', 'delta_do_zaplaty_zl',
        ]
        for col in round_cols:
            if col in show_fv.columns:
                show_fv[col] = show_fv[col].round(1)
        for col in ['delta_kwh_pct', 'delta_energia_pct', 'delta_brutto_pct', 'delta_do_zaplaty_pct']:
            if col in show_fv.columns:
                show_fv[col] = show_fv[col].round(1)

        display_cols = [
            c
            for c in [
                'okres',
                'prognoza_energia_zl',
                'faktura_energia_zl',
                'delta_energia_zl',
                'delta_energia_pct',
                'prognoza_kwh',
                'faktura_kwh',
                'delta_kwh',
                'delta_kwh_pct',
                'prognoza_do_zaplaty_zl',
                'faktura_do_zaplaty_zl',
                'delta_do_zaplaty_zl',
                'miesiecy_faktur',
                'typ_faktur',
            ]
            if c in show_fv.columns
        ]
        st.dataframe(show_fv[display_cols], use_container_width=True, hide_index=True)

        chart_df = complete_energy.copy()
        if not chart_df.empty:
            st.markdown('**Koszt energii netto [zł]** — najbliżej widoku w app Tauron')
            cost_chart = chart_df.set_index('okres')[['prognoza_energia_zl', 'faktura_energia_zl']]
            st.line_chart(cost_chart)

        incomplete = fv[fv['miesiecy_faktur'] < 2]
        if not incomplete.empty:
            st.warning(
                'Niepełne okresy (brak faktur za oba miesiące blankietu): '
                + ', '.join(incomplete['okres'].astype(str).tolist())
            )

        highlight = fv[fv['okres'].isin(['2025-11 – 2025-12', '2026-01 – 2026-02'])]
        if not highlight.empty:
            for _, row in highlight.iterrows():
                st.caption(
                    f"**{row['okres']}** · energia {row['delta_energia_zl']:+.0f} zł "
                    f"({row['delta_energia_pct']:+.0f}%) · pobór {row['delta_kwh']:+.0f} kWh "
                    f"({row['delta_kwh_pct']:+.0f}%) · faktury: {row.get('typ_faktur', '—')}"
                )

        korekta_rows = fv[fv['typ_faktur'].astype(str).str.contains('korekta', case=False, na=False)]
        if not korekta_rows.empty:
            st.info(
                'Okresy z **korektą** (np. styczeń 2026): koszt energii netto jest OK, '
                'ale kolumna „do zapłaty” jest pominięta — korekta to pełna kwota, nie delta miesięczna.'
            )

with tab_deposit:
    st.subheader('Depozyt prosumencki — kalkulator i historia')
    render_deposit_panel(show_chart=True)

with tab_forecast:
    st.subheader('Closeouty: prognoza RF vs aplikacja FoxESS')
    val = load_forecast_validation()
    summary = validation_summary(val)
    if summary:
        m1, m2, m3 = st.columns(3)
        m1.metric('Dni w walidacji', summary.get('n_days', '—'))
        m2.metric(
            'MAE raw ~5:00',
            f"{summary['mae_raw_5']:.1f} kWh" if 'mae_raw_5' in summary else '—',
        )
        m3.metric(
            'MAE raw ~12:00',
            f"{summary['mae_raw_12']:.1f} kWh" if 'mae_raw_12' in summary else '—',
        )

    if val.empty:
        st.warning('Brak data/processed/forecasts/forecast_validation.csv — uruchom evening_closeout.')
    else:
        cols = [
            c
            for c in [
                'target_day',
                'actual_pv_total',
                'predicted_daily_raw',
                'predicted_midday_raw',
                'best_snapshot_raw_label',
                'best_snapshot_raw_error_kwh',
                'predicted_daily',
                'predicted_midday',
            ]
            if c in val.columns
        ]
        st.dataframe(val[cols].sort_values('target_day'), use_container_width=True, hide_index=True)

        plot_df = val.copy()
        if 'target_day' in plot_df.columns and 'actual_pv_total' in plot_df.columns:
            plot_df = plot_df.sort_values('target_day')
            chart = pd.DataFrame({'dzień': plot_df['target_day'].astype(str)})
            chart = chart.set_index('dzień')
            if 'actual_pv_total' in plot_df.columns:
                chart['app'] = plot_df['actual_pv_total'].values
            if 'predicted_daily_raw' in plot_df.columns:
                chart['raw_5'] = plot_df['predicted_daily_raw'].values
            if 'predicted_midday_raw' in plot_df.columns:
                chart['raw_12'] = plot_df['predicted_midday_raw'].values
            st.line_chart(chart)

    st.caption('Raw = sam RF · hybryda w CSV to FoxESS+RF (nie ADJUST). Korekta operacyjna OFF.')

with tab_about:
    st.markdown(
        '''
### Zakres MVP
- miejsce na **ręczne wpisy pogodowe** → tabela `weather_notes`
- **wpis faktur Tauron** → `tauron_bills` (+ opcjonalnie `tauron_tariff`, `meter_readings`)
- **depozyt prosumencki** — poz. 4–6 z faktur (saldo + historia)
- podgląd **prognoza vs faktura** (blankiety 2-miesięczne vs suma rachunków)
- podgląd **dokładności** prognoz vs app
- bez wrzucania notatek / rachunków do RF

### Tauron vs model PV
- dane z faktur służą **ROI i walidacji biznesowej**
- **nie** są cechą ani targetem modelu PV (eliminacja data leakage)

### Eksperymenty ML
- **Na produkcji (dual launchd):** 16 cech + **CS4** (`daily_cs4` / `midday_cs4` / `peak_cs4`)
- Niedziela: `train_dual_weekly.sh` trenuje oba modele
- UKMO: tylko testy (`./scripts/analysis/run_ukmo_tests.sh`)
- Geometria / adjust: park

### Uruchomienie
```bash
cd /path/to/smart-energy-model
source venv/bin/activate
pip install streamlit   # raz
streamlit run dashboard/app.py
```
'''
    )
