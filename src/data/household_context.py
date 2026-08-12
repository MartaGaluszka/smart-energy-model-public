"""
Kontekst użytkowania domu — okresy do analizy EDA / ROI / ML.

Okres remontowy vs normalne mieszkanie. ROI i optymalizacja baterii od IX 2025;
osobne okno pod czystą predykcję PV w miesiącach wysokiego oddawania (II 2026+).
"""

from datetime import date
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

PeriodLabel = Literal['renovation', 'normal', 'high_export', 'pre_contract']

# Faza obecności / zużycia — do EDA, porównań miesięcznych i ML (wykluczanie outlierów).
OccupancyPhase = Literal[
    'pre_contract',
    'forecast_settlement',
    'inverter_misconfig',
    'empty_house',
    'cooking_only',
    'full_occupancy',
    'pre_trip_cooking',
    'away_camping',
]

# Umowa Tauron od 28.03.2025 (formalny start kontraktu)
CONTRACT_START = date(2025, 3, 28)

# Fizyczny start poboru: bezpieczniki załączone, licznik rejestruje zużycie (~21.04.2025).
# Wcześniej umowa była, ale prąd nie był dostępny — pierwsza faktura to prognoza operatora.
GRID_PHYSICAL_START = date(2025, 4, 21)

# Korekta / rozliczenie 28.03–24.04 (333 kWh) — prognoza, którą Tauron wystawił do zapłaty.
# Nie porównywać 1:1 z licznikiem; wiarygodne odczyty od GRID_PHYSICAL_START.
FORECAST_FIRST_SETTLEMENT_END = date(2025, 4, 24)

# Remont i suszenie posadzek betonowych
RENOVATION_START = date(2025, 3, 28)
RENOVATION_END = date(2025, 8, 31)

# Normalne użytkowanie: rodzina 2+1, praca zdalna (spanie + CWU w domu)
NORMAL_USAGE_START = date(2025, 9, 1)

# --- Fazy obecności / profilu zużycia (uzgodnione z użytkownikiem) ---
# VI–VII 2025: dom pusty (spanie gdzie indziej, bez gotowania).
EMPTY_HOUSE_START = date(2025, 6, 1)
EMPTY_HOUSE_END = date(2025, 7, 31)

# VIII 2025: gotowanie w domu, spanie gdzie indziej, bez podgrzewania wody użytkowej.
COOKING_ONLY_START = date(2025, 8, 1)
COOKING_ONLY_END = date(2025, 8, 31)

# VI 2026: gotowanie na zapas przed kempingiem, potem ~10 dni pustego domu.
PRE_TRIP_COOKING_START = date(2026, 6, 1)
PRE_TRIP_COOKING_END = date(2026, 6, 16)


@dataclass(frozen=True)
class AwayTrip:
    """Pojedynczy wyjazd — pusty dom (minimalny standby, PV → eksport)."""
    start: date
    end: date
    label: str
    source: Literal['user', 'foxess_detected', 'foxess_inferred']
    notes: str = ''


# Wyjazdy zapisane w repo — nie trzeba pamiętać dat.
# Źródło foxess_*: wykryte z niskiego load; można skorygować po potwierdzeniu z kalendarza.
AWAY_TRIPS: tuple[AwayTrip, ...] = (
    AwayTrip(
        date(2025, 9, 18),
        date(2025, 9, 21),
        'wyjazd jesienny (~4 dni)',
        'foxess_detected',
    ),
    AwayTrip(
        date(2026, 2, 7),
        date(2026, 2, 14),
        'wyjazd zimowy (~tydzień)',
        'user',
        notes=(
            'Pusty dom: niepotrzebne urządzenia odłączone od sieci, routery I/II piętro wyłączone. '
            'Sterownik grzania na partii (parter) — obniżenie setpoint tylko na parterze 21→17°C; '
            'I i II piętro bez zdalnej regulacji (brak routerów). '
            'Pogoda: w trakcie wyjazdu ocieplenie (12–13 II do ~14°C); po powrocie znów mrozy do ~-13°C.'
        ),
    ),
    AwayTrip(
        date(2026, 6, 17),
        date(2026, 6, 30),
        'kemping (pusty dom)',
        'user',
    ),
)

# Wsteczna kompatybilność (kemping VI 2026)
AWAY_CAMPING_START = AWAY_TRIPS[-1].start
AWAY_CAMPING_END = AWAY_TRIPS[-1].end

OCCUPANCY_PHASE_NOTES: dict[OccupancyPhase, str] = {
    'pre_contract': 'Przed umową Tauron — brak danych licznika.',
    'forecast_settlement': 'Umowa od 28.03, bezpieczniki ~21.04; pierwsza faktura to prognoza operatora.',
    'inverter_misconfig': 'Błędne ustawienia falownika — PV nie odzwierciedla pogody; dom pusty.',
    'empty_house': 'Dom pusty: brak gotowania i noclegu; prawie cała PV → sieć.',
    'cooking_only': 'Gotowanie w domu, spanie gdzie indziej, bez CWU — częściowa autokonsumpcja.',
    'full_occupancy': 'Normalne mieszkanie (2+1, praca zdalna, CWU, bateria od IX 2025).',
    'pre_trip_cooking': 'Intensywne gotowanie na zapas przed wyjazdem — wysoka autokonsumpcja.',
    'away_camping': 'Pusty dom (kemping) — minimalny standby, PV głównie na eksport.',
}

OCCUPANCY_PHASE_LABELS_PL: dict[OccupancyPhase, str] = {
    'pre_contract': 'przed umową',
    'forecast_settlement': 'prognoza operatora',
    'inverter_misconfig': 'błąd falownika',
    'empty_house': 'dom pusty',
    'cooking_only': 'tylko gotowanie',
    'full_occupancy': 'pełne użytkowanie',
    'pre_trip_cooking': 'gotowanie przed wyjazdem',
    'away_camping': 'kemping (dom pusty)',
}

# Główny start analiz (ROI, pogoda, bateria, ML) — uzgodnione z użytkownikiem
PRIMARY_ANALYSIS_START = NORMAL_USAGE_START

# ROI: prognoza Tauron vs rzeczywistość
ROI_ANALYSIS_START = PRIMARY_ANALYSIS_START

# Sterowanie baterią / optymalizacja G12w — od normalnego mieszkania.
# Kluczowe okresy przejściowe (jesień, wiosna): ogrzewanie + umiarkowana produkcja PV,
# ryzyko braku 2–3 h przed wschodem słońca lub pobór z sieci w droższej strefie dziennej.
ML_BATTERY_START = PRIMARY_ANALYSIS_START

# Predykcja produkcji PV (XGBoost) — miesiące z wysokim oddawaniem, stabilny profil
ML_PV_FORECAST_START = date(2026, 2, 1)

# --- ML split: Development vs Production Holdout ---
# Development: pełny cykl sezonowy do końca maja 2026.
# Production Holdout: dane niewidziane w treningu (czerwiec–lipiec 2026, cut-off sync).
DEVELOPMENT_END = date(2026, 5, 31)
PRODUCTION_HOLDOUT_START = date(2026, 6, 1)
PRODUCTION_HOLDOUT_END = date(2026, 7, 9)

# Wsteczna kompatybilność
ML_PROSUMER_START = ML_PV_FORECAST_START

# FoxESS — pierwsze dane w chmurze (instalacja ~25.04.2025)
FOXESS_DATA_START = date(2025, 4, 25)

# Oficjalny opis okresu (prezentacja / praca) — uzgodniony z użytkownikiem:
PV_INVERTER_PERIOD_NOTE = (
    '21.04–29.05.2025: błędne ustawienia falownika hybrydowego (tryb pracy / priorytet '
    'baterii w aplikacji FoxESS) — produkcja PV nie odzwierciedlała pogody. '
    'Od 30.05.2025: zmiana ustawień na maksymalną produkcję prądu.'
)

# Wykluczyć z korelacji pogoda↔PV i treningu ML. (Falownik = inwerter.)
PV_INVERTER_MISCONFIG_START = GRID_PHYSICAL_START
PV_INVERTER_MISCONFIG_END = date(2025, 5, 29)
PV_WEATHER_VALID_START = date(2025, 5, 30)

# Ciągła seria FoxESS: po zmianie ustawień (30.05) + po luce API w V 2025 (brak 12–26.05)
FOXESS_RELIABLE_START = date(2025, 6, 1)

# Odczyty licznika (portal Tauron) — od fizycznego startu poboru (= GRID_PHYSICAL_START)
METER_DATA_START = GRID_PHYSICAL_START

# Pogoda Open-Meteo — od startu danych licznika (okres remontu + analiza)
WEATHER_DATA_START = METER_DATA_START

# Wykrywanie anomalii — odłożone (decyzja użytkownika); szkice okien na przyszłość:
ANOMALY_DEFERRED = True
ANOMALY_PV_START = FOXESS_DATA_START
ANOMALY_BEHAVIOR_START = PRIMARY_ANALYSIS_START
# Trening detektora PV: od normalnego użytkowania, ale baseline sezonowy (nie jeden profil „zdrowy”).
ANOMALY_TRAIN_START = PRIMARY_ANALYSIS_START

# Reguły PV — „słońce bez produkcji” nie zawsze anomalia:
ANOMALY_PV_RULES = {
    'misconfig': (
        '21.04–29.05.2025: błędne ustawienia falownika (tryb pracy / bateria w app FoxESS) — '
        'produkcja do pełności baterii. Case study, nie trenować jako „zdrowy” baseline.'
    ),
    'winter_snow': (
        'Zima: słoneczny dzień + śnieg na panelach → brak/niska produkcja mimo radiacji. '
        'To oczekiwane zachowanie, nie awaria falownika. Wymaga temp./opadów/śniegu w modelu.'
    ),
    'true_anomaly': (
        'Podejrzane: wiosna–lato–jesień, brak śniegu, wysoka radiacja, PV << oczekiwane. '
        'Baseline per sezon (shoulder/summer), zima osobno z flagą „śnieg”.'
    ),
}

BatterySeason = Literal['winter', 'shoulder', 'summer']

# Strategia użytkowania baterii (obserwacje użytkownika, G12w)
BATTERY_STRATEGY = {
    'shoulder': (
        'Wiosna–jesień: bateria na użytkowanie nocne — mostek do wschodu słońca. '
        'Prognoza pogody decyduje, czy starczy do produkcji PV; przy zachmurzeniu '
        'ryzyko poboru z drogiej strefy dziennej G12w.'
    ),
    'winter': {
        'summary': (
            'Zima: mało PV — ForceCharge w taniej strefie G12w: noc 22:00–6:00 '
            'oraz ~2 h w pasie 13:00–15:00 (pon–pt). Cel: ~90% zużycia z tańszej strefy. '
            'Weekendy/święta: cała doba tania.'
        ),
        'away_checklist': (
            'Wi‑Fi: zostaw router lub AP w zasięgu sterowników grzania na parterze, I i II piętrze — '
            'inaczej nie obniżysz setpointu zdalnie (II 2026: wyłączone routery pięter).',
            'Ogrzewanie: obniż temperaturę na każdym poziomie osobno przed wyjazdem (np. 21→17°C); '
            'tylko parter to ok. 1/3 oszczędności (case II 2026).',
            'Urządzenia: odłącz niepotrzebne od sieci; zostaw minimum (lodówka, falownik, router do grzania).',
            'Bateria: przy pustym domu rozważ mniejszy ForceCharge — niski load, PV i tak idzie głównie na eksport.',
            'Po powrocie: sprawdź setpointy na wszystkich poziomach — po falach mrozów może być potrzebne dogrzanie.',
        ),
    },
    'summer': (
        'Lato: duża produkcja PV, bateria uzupełnia autokonsumpcję; mniejsza rola '
        'ładowania z sieci.'
    ),
}

HOUSEHOLD_NOTES = (
    'Umowa 28.03.2025, ale bezpieczniki załączone dopiero ~21.04 — wtedy realny start prądu. '
    'Pierwsza faktura (korekta 28.03–24.04, 333 kWh) to prognoza operatora, nie profil licznika. '
    'Remont 28.03–31.08.2025. VI–VII 2025: dom pusty (spanie gdzie indziej). '
    'VIII 2025: gotowanie w domu, bez CWU, spanie gdzie indziej. '
    'Od 01.09.2025 normalne mieszkanie (2+1, praca zdalna). '
    'Wyjazdy (pusty dom): IX 2025 18–21, II 2026 7–14, VI 2026 kemping 17–30. '
    'VI 2026: gotowanie na zapas (1–16), potem kemping — pusty dom (~17–30). '
    + PV_INVERTER_PERIOD_NOTE + ' '
    'Główna analiza (ROI, pogoda, bateria) od 01.09.2025. Licznik wiarygodny od 21.04.2025. '
    'Anomalie PV: zima+śnieg na panelach = brak produkcji mimo słońca (nie anomalia). '
    'Anomalie — odłożone. Predykcja PV (duże oddawanie) od II.2026. '
    'Skok poboru XI 2025 (567 kWh): początek sezonu grzewczego. '
    + BATTERY_STRATEGY['shoulder'] + ' ' + BATTERY_STRATEGY['winter']['summary']
)


def battery_strategy_text(season: BatterySeason) -> str:
    """Tekst strategii baterii dla sezonu (shoulder / winter / summer)."""
    val = BATTERY_STRATEGY[season]
    if isinstance(val, dict):
        return val['summary']
    return val


def winter_away_checklist() -> tuple[str, ...]:
    """Checklist przed zimowym wyjazdem (pusty dom)."""
    winter = BATTERY_STRATEGY['winter']
    assert isinstance(winter, dict)
    return winter['away_checklist']


def battery_season(month: int) -> BatterySeason:
    """Sezon pod strategię baterii (miesiąc 1–12)."""
    if month in (12, 1, 2):
        return 'winter'
    if month in (6, 7, 8):
        return 'summer'
    return 'shoulder'


def classify_period(d: date) -> PeriodLabel:
    """Zwraca etykietę okresu dla danej daty."""
    if d < CONTRACT_START:
        return 'pre_contract'
    if RENOVATION_START <= d <= RENOVATION_END:
        return 'renovation'
    if d >= ML_PV_FORECAST_START:
        return 'high_export'
    return 'normal'


def away_trip_for_date(d: date) -> Optional[AwayTrip]:
    """Zwraca wyjazd obejmujący datę lub None."""
    for trip in AWAY_TRIPS:
        if trip.start <= d <= trip.end:
            return trip
    return None


def is_away_trip(d: date) -> bool:
    return away_trip_for_date(d) is not None


def is_atypical_load_day(d: date) -> bool:
    """
    Dzień nietypowego zużycia — wykluczyć z baseline load / kalibracji baterii.

    Obejmuje wyjazdy, gotowanie przed wyjazdem, okresy remontu / pustego domu.
    """
    phase = classify_occupancy(d)
    return phase in (
        'away_camping',
        'pre_trip_cooking',
        'empty_house',
        'cooking_only',
        'inverter_misconfig',
        'forecast_settlement',
    )


def classify_occupancy(d: date) -> OccupancyPhase:
    """Faza obecności / profilu zużycia dla danej daty (priorytet: okna szczegółowe)."""
    if d < CONTRACT_START:
        return 'pre_contract'
    if is_forecast_settlement_period(d):
        return 'forecast_settlement'
    if is_pv_inverter_misconfigured(d):
        return 'inverter_misconfig'
    if is_away_trip(d):
        return 'away_camping'
    if PRE_TRIP_COOKING_START <= d <= PRE_TRIP_COOKING_END:
        return 'pre_trip_cooking'
    if COOKING_ONLY_START <= d <= COOKING_ONLY_END:
        return 'cooking_only'
    if EMPTY_HOUSE_START <= d <= EMPTY_HOUSE_END:
        return 'empty_house'
    if d >= NORMAL_USAGE_START:
        return 'full_occupancy'
    if d >= PV_WEATHER_VALID_START:
        return 'empty_house'
    return 'forecast_settlement'


def occupancy_label_pl(d: date) -> str:
    """Polska etykieta fazy obecności."""
    return OCCUPANCY_PHASE_LABELS_PL[classify_occupancy(d)]


def occupancy_note(d: date) -> str:
    """Opis fazy obecności."""
    return OCCUPANCY_PHASE_NOTES[classify_occupancy(d)]


def month_occupancy_phases(year: int, month: int) -> list[OccupancyPhase]:
    """Unikalne fazy obecności w danym miesiącu kalendarzowym."""
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    phases: list[OccupancyPhase] = []
    seen: set[OccupancyPhase] = set()
    for day in range(1, last_day + 1):
        phase = classify_occupancy(date(year, month, day))
        if phase not in seen:
            seen.add(phase)
            phases.append(phase)
    return phases


def month_occupancy_label(year: int, month: int) -> str:
    """Etykieta miesiąca do tabel EDA (jedna faza lub połączenie)."""
    phases = month_occupancy_phases(year, month)
    return ' + '.join(OCCUPANCY_PHASE_LABELS_PL[p] for p in phases)


def add_occupancy_labels_to_months(months: list[str]) -> list[dict]:
    """
    Dla listy 'YYYY-MM' zwraca słowniki z fazą obecności.

    Przykład: add_occupancy_labels_to_months(['2025-08', '2026-06'])
    """
    rows = []
    for ym in months:
        year, month = map(int, ym.split('-'))
        rows.append({
            'month': ym,
            'occupancy_phase': month_occupancy_label(year, month),
            'occupancy_phases': month_occupancy_phases(year, month),
        })
    return rows


def is_renovation_period(d: date) -> bool:
    return classify_period(d) == 'renovation'


def is_normal_usage_period(d: date) -> bool:
    return d >= NORMAL_USAGE_START


def is_grid_physical_period(d: date) -> bool:
    """True od fizycznego startu poboru (bezpieczniki, odczyty licznika)."""
    return d >= GRID_PHYSICAL_START


def is_forecast_settlement_period(d: date) -> bool:
    """Okres pierwszej prognozowanej faktury — nie wiarygodny vs licznik."""
    return CONTRACT_START <= d <= FORECAST_FIRST_SETTLEMENT_END


def is_pv_inverter_misconfigured(d: date) -> bool:
    """PV FoxESS nie odzwierciedla pogody (limit baterii, błędne ustawienia falownika)."""
    return PV_INVERTER_MISCONFIG_START <= d <= PV_INVERTER_MISCONFIG_END


def is_pv_weather_valid(d: date) -> bool:
    """Produkcja PV sensowna do korelacji z pogodą i treningu modelu."""
    return d >= PV_WEATHER_VALID_START and not is_pv_inverter_misconfigured(d)


def is_ml_battery_period(d: date) -> bool:
    return d >= ML_BATTERY_START


def is_ml_pv_forecast_period(d: date) -> bool:
    return d >= ML_PV_FORECAST_START


# alias
is_ml_prosumer_period = is_ml_pv_forecast_period


def analysis_periods() -> dict:
    """Rekomendowane okna analizy."""
    return {
        'full_history': (CONTRACT_START.isoformat(), None),
        'forecast_settlement': (CONTRACT_START.isoformat(), FORECAST_FIRST_SETTLEMENT_END.isoformat()),
        'grid_physical': (GRID_PHYSICAL_START.isoformat(), None),
        'renovation_only': (RENOVATION_START.isoformat(), RENOVATION_END.isoformat()),
        'primary': (PRIMARY_ANALYSIS_START.isoformat(), None),
        'roi': (ROI_ANALYSIS_START.isoformat(), None),
        'meter_data': (METER_DATA_START.isoformat(), PRIMARY_ANALYSIS_START.isoformat()),
        'ml_battery': (ML_BATTERY_START.isoformat(), None),
        'ml_pv_forecast': (ML_PV_FORECAST_START.isoformat(), None),
        'normal_usage': (NORMAL_USAGE_START.isoformat(), None),
        'foxess_data': (FOXESS_DATA_START.isoformat(), None),
        'pv_inverter_misconfig': (
            PV_INVERTER_MISCONFIG_START.isoformat(),
            PV_INVERTER_MISCONFIG_END.isoformat(),
        ),
        'pv_inverter_period_note': PV_INVERTER_PERIOD_NOTE,
        'pv_weather_valid': (PV_WEATHER_VALID_START.isoformat(), None),
        'foxess_reliable': (FOXESS_RELIABLE_START.isoformat(), None),
        'anomaly_pv': (ANOMALY_PV_START.isoformat(), None),
        'anomaly_behavior': (ANOMALY_BEHAVIOR_START.isoformat(), None),
        'anomaly_train': (ANOMALY_TRAIN_START.isoformat(), None),
        'anomaly_pv_rules': ANOMALY_PV_RULES,
        'notes': HOUSEHOLD_NOTES,
        'battery_strategy': BATTERY_STRATEGY,
        'winter_away_checklist': winter_away_checklist(),
        'occupancy_empty_house': (
            EMPTY_HOUSE_START.isoformat(),
            EMPTY_HOUSE_END.isoformat(),
        ),
        'occupancy_cooking_only': (
            COOKING_ONLY_START.isoformat(),
            COOKING_ONLY_END.isoformat(),
        ),
        'occupancy_pre_trip_cooking': (
            PRE_TRIP_COOKING_START.isoformat(),
            PRE_TRIP_COOKING_END.isoformat(),
        ),
        'occupancy_away_camping': (
            AWAY_CAMPING_START.isoformat(),
            AWAY_CAMPING_END.isoformat(),
        ),
        'away_trips': [
            {
                'start': t.start.isoformat(),
                'end': t.end.isoformat(),
                'label': t.label,
                'source': t.source,
                'notes': t.notes,
            }
            for t in AWAY_TRIPS
        ],
        'occupancy_phase_notes': OCCUPANCY_PHASE_NOTES,
        'occupancy_phase_labels_pl': OCCUPANCY_PHASE_LABELS_PL,
    }


def roi_date_range(end: Optional[date] = None) -> Tuple[str, str]:
    """Domyślny zakres dat do obliczeń ROI."""
    end_d = end or date.today()
    return ROI_ANALYSIS_START.isoformat(), end_d.isoformat()


def ml_battery_date_range(end: Optional[date] = None) -> Tuple[str, str]:
    """Zakres dat do treningu sterowania baterią i optymalizacji G12w."""
    end_d = end or date.today()
    return ML_BATTERY_START.isoformat(), end_d.isoformat()


def ml_pv_date_range(end: Optional[date] = None) -> Tuple[str, str]:
    """Zakres dat do predykcji produkcji PV (wysokie oddawanie)."""
    end_d = end or date.today()
    return ML_PV_FORECAST_START.isoformat(), end_d.isoformat()


def ml_date_range(end: Optional[date] = None) -> Tuple[str, str]:
    """Domyślny zakres ML — optymalizacja baterii (od IX 2025)."""
    return ml_battery_date_range(end)


def production_holdout_range() -> Tuple[str, str]:
    """Zakres Production Holdout (dokumentacja + ewaluacja modelu PV)."""
    return PRODUCTION_HOLDOUT_START.isoformat(), PRODUCTION_HOLDOUT_END.isoformat()


def development_date_range() -> Tuple[str, str]:
    """Zakres Development Set dla modelu PV (12 mies., pełny cykl)."""
    return FOXESS_RELIABLE_START.isoformat(), DEVELOPMENT_END.isoformat()
