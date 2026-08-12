"""
Ground truth z obserwacji pogodowych — wyłącznie opisy tekstowe (bez plików graficznych w repo).

Zdjęcia/filmy z forum osiedlowego lub telefonu trzymasz lokalnie; w projekcie są tylko:
daty, godziny, opisy nieba/śniegu i klasy jakościowe w PHOTO_METADATA / CSV.

Klasy:
    snow_panel_block  — Typ A: śnieg na panelach, PV ~0 mimo radiacji
    snow_landscape    — Typ B: śnieg w otoczeniu, panele pracują
    fog               — mgła w godzinach produkcji
    clear_sunny       — słońce, brak śniegu na dachach
    partial_cloud     — przejaśnienia / patchwork, wysokie PV mimo chmur w modelu
    overcast_white    — białe chmury, całe niebo, umiarkowane PV
    overcast_heavy    — janoszare / ciężkie zachmurzenie, niskie PV
    no_snow           — brak pokrywy, dzień przejściowy
    artifact          — wyklucz z metryk (FoxESS)
    evening_obs       — obserwacja po zmroku; klasa dzienna z PV/API
"""

from __future__ import annotations

from typing import List, Tuple

DEFAULT_PHOTO_VALIDATION = (
    '2025-11-21:snow,2025-11-23:snow,2025-11-24:snow,2025-11-27:snow,2025-11-28:other,2025-11-29:other,'
    '2025-12-04:other,2025-12-09:other,2025-12-13:sun,2025-12-15:fog,2025-12-16:other,2025-12-29:fog,2025-12-30:other,2025-12-31:snow,'
    '2026-01-01:snow,2026-01-03:other,2026-01-09:snow,2026-01-13:snow,2026-01-19:snow,2026-01-20:snow,2026-01-21:snow,2026-01-22:snow,2026-01-26:snow,2026-01-27:snow,'
    '2026-02-01:snow,2026-02-03:sun,2026-02-07:other,2026-02-12:sun,2026-02-14:other,2026-02-11:snow,2026-02-17:snow,2026-02-18:snow,2026-02-20:snow,2026-02-28:sun'
)

PHOTO_METADATA: dict[str, dict[str, str]] = {
    '2025-11-21': {'photo_time': '08:30', 'photo_snow_cm': '~3', 'photo_sky': 'pochmurno', 'photo_notes': 'lekki snieg'},
    '2025-11-23': {
        'photo_time': '10:01',
        'photo_snow_cm': '10-15',
        'photo_sky': 'bezchmurne',
        'photo_notes': 'snieg na dachu, PV=0 mimo slonca',
    },
    '2025-11-24': {
        'photo_time': '07:03; 12:20',
        'photo_snow_cm': '~10',
        'photo_sky': 'sloneczny; ~10% chmur (poludnie)',
        'photo_notes': '07:03 sloneczny, ~10cm na dachach sasiadow; 12:20 ~10cm, pojedyncze chmury, PV=0 caly dzien (Typ A)',
    },
    '2025-11-27': {
        'photo_time': '11:21',
        'photo_snow_cm': 'ogrodek; sasiadzi: panele 90-100% bez sniegu',
        'photo_sky': 'szaro-biale',
        'photo_notes': 'sasiadzi panele czyste, snieg w ogrodku; wlasna PV 9-16h ~0,9 kWh (niska — panele domu prawdop. nadal zasniezone)',
    },
    '2025-11-28': {
        'photo_time': '12:49',
        'photo_snow_cm': 'do 5 (trawnik); 0 na widocznych dachach',
        'photo_sky': 'slonecznie, błekitne niebo ~10% bialych chmur',
        'photo_notes': 'Typ B: snieg na ziemi, dachy czyste; PV 9-16h ~11 kWh',
    },
    '2025-11-29': {
        'photo_time': '19:34',
        'photo_snow_cm': '0',
        'photo_sky': 'wieczor',
        'photo_notes': 'brak pokrywy snieznej (topnienie po 23-24 XI), PV 9-16h ~2 kWh',
    },
    '2025-12-04': {
        'photo_time': '10:12 (2 kadry)',
        'photo_sky': 'kadr1: ~80% jasnoszare/biale chmury; kadr2: błekitne niebo ~10% chmur',
        'photo_notes': 'niebo patchwork; PV 9-16h ~9,3 kWh',
    },
    '2025-12-09': {
        'photo_time': '15:36',
        'photo_sky': 'janoszare chmury, cale niebo',
        'photo_notes': 'ciezkie zachmurzenie; PV 9-16h ~2,1 kWh',
    },
    '2025-12-13': {'photo_time': '11:47', 'photo_sky': 'slonce', 'photo_notes': 'brak sniegu, dzien referencyjny'},
    '2025-12-15': {'photo_time': '10:06', 'photo_sky': 'mgla', 'photo_notes': 'brak sniegu'},
    '2025-12-16': {
        'photo_time': '13:05',
        'photo_snow_cm': '0',
        'photo_sky': 'cale niebo w bialych chmurach',
        'photo_notes': 'pochmurno bez sniegu (nie mgla); PV 9-16h ~3 kWh',
    },
    '2025-12-29': {
        'photo_time': '17:09',
        'photo_sky': 'troche mglisto, po zachodzie slonca',
        'photo_notes': 'foto wieczorne; PV 9-16h ~0,6 kWh (pochmurnosc w dzien)',
    },
    '2025-12-30': {
        'photo_time': '16:43 (film)',
        'photo_snow_cm': '0 (widocznie)',
        'photo_sky': 'po zmroku, brak mgly',
        'photo_notes': 'film wieczorny; PV 9-16h ~6,3 kWh',
    },
    '2025-12-31': {
        'photo_time': '23:55',
        'photo_snow_cm': '~3',
        'photo_sky': 'zachmurzenie',
        'photo_notes': 'Typ A: PV 9-16h ~0,55 kWh mimo radiacji ~1,1 kWh/m2',
    },
    '2026-01-01': {
        'photo_time': '00:07',
        'photo_snow_cm': '~3',
        'photo_sky': 'zachmurzenie, sylwester',
        'photo_notes': 'Typ B/granica; PV 9-16h ~4,7 kWh',
    },
    '2026-01-03': {
        'photo_time': '22:02',
        'photo_snow_cm': '0',
        'photo_sky': 'wieczor',
        'photo_notes': 'brak sniegu; PV 9-16h ~8,3 kWh',
    },
    '2026-01-09': {
        'photo_time': '09:39; 09:43',
        'photo_snow_cm': 'sasiad 09:43: 2 segmenty paneli 70-80% odsniezone; sasiad 09:39: 3 segmenty calkowicie zakryte',
        'photo_sky': 'sloneczny dzien, niebieskie niebo',
        'photo_notes': 'Typ A u sasiadow (slonce + snieg na panelach); wlasna instalacja PV 9-16h ~10,5 kWh — panele domu prawdop. czyste lub czesciowo',
    },
    '2026-01-13': {
        'photo_time': '12:08; 13:55; 16:21',
        'photo_snow_cm': '~15; dachy N i E zaśnieżone (12:08, 16:21); ogrodek ~15 (16:21)',
        'photo_sky': '12:08: szaro-biale, pruszenie; 13:55: niebo niewidoczne, chmury; 16:21: po zachodzie, niebieskie lub szare (niepewne)',
        'photo_notes': 'artefakt FoxESS (-36 kWh) — wyklucz z kalibracji yield; 12:08 widok N+E, dachy zaśnieżone ~15cm, delikatny opad; od strony PV slonce moglo przytopic snieg (panele prawdop. czyste); PV 9-16h ~7 kWh',
    },
    '2026-01-19': {
        'photo_time': '15:18',
        'photo_snow_cm': '~10 (nie na wszystkich dachach)',
        'photo_sky': 'bezchmurne, slonce',
        'photo_notes': 'Typ B; PV 9-16h ~12,3 kWh',
    },
    '2026-01-20': {
        'photo_time': '15:24',
        'photo_snow_cm': '~10 (nie na wszystkich dachach)',
        'photo_sky': 'bezchmurne, slonce',
        'photo_notes': 'Typ B; PV 9-16h ~11,3 kWh',
    },
    '2026-01-21': {
        'photo_time': '12:44',
        'photo_snow_cm': 'dach 1/4 powierzchni; ogrodek; 0 na panelach',
        'photo_sky': 'sloneczny dzien, niebieskie niebo',
        'photo_notes': 'Typ B: snieg na czesci dachu i w ogrodku, panele czyste; PV 9-16h ~13,8 kWh',
    },
    '2026-01-22': {
        'photo_time': '11:44; 11:45',
        'photo_snow_cm': '~10 (nie na wszystkich dachach)',
        'photo_sky': 'zachmurzenie — biale chmury, prawie cale niebo',
        'photo_notes': 'Typ B; PV 9-16h ~8 kWh',
    },
    '2026-01-26': {
        'photo_time': '14:02',
        'photo_snow_cm': 'w ogrodzie; 0 na panelach',
        'photo_sky': 'jasne chmury; przeswitujace slonce miedzy chmurami',
        'photo_notes': 'Typ B; brak sniegu na panelach; PV 9-16h ~4 kWh (niskie kWh, yield ~85% ref — slonce rozproszone)',
    },
    '2026-01-27': {
        'photo_time': '19:22 (czas forum — niewiarygodny; wykonanie: nieznane, prawdop. 11–15)',
        'photo_snow_cm': 'ogrodek do ~5; dach 1/3 zasniezony (strona bez paneli)',
        'photo_sky': 'delikatnie niebieskawe / szare (dzienne, nie zmrok)',
        'photo_notes': 'Typ B: widok od polnocy (domy od strony N); brak cieni na zdjeciu (swiatlo rozproszone, pochmurno); snieg na dachu po stronie bez paneli; PV 9-16h ~5,5 kWh; godz. forum 19:22 niemozliwa — zweryfikowac EXIF',
    },
    '2026-02-01': {
        'photo_time': '13:18',
        'photo_snow_cm': 'do ~3',
        'photo_sky': 'szare chmury, cale niebo',
        'photo_notes': 'Typ B; PV 9-16h ~10,8 kWh mimo zachmurzenia',
    },
    '2026-02-03': {
        'photo_time': 'nieznana',
        'photo_sky': 'mocne slonce (jedyna obserwacja ze zdjecia)',
        'photo_notes': 'brak info o sniegu/dachach; PV 9-16h ~16,2 kWh; OM: chmury ~79%, snieg ~4cm',
    },
    '2026-02-07': {
        'photo_time': '07:59',
        'photo_snow_cm': '0 na dachach',
        'photo_sky': 'biale chmury',
        'photo_notes': 'rano przed 9h; brak sniegu na dachach; PV 9-16h ~3,8 kWh',
    },
    '2026-02-11': {
        'photo_time': '11:57',
        'photo_snow_cm': 'plamy na trawniku (gdzie bylo grubiej); 0 na panelach',
        'photo_sky': 'slonce',
        'photo_notes': 'Typ B; brak sniegu na panelach; PV 9-16h ~6,7 kWh',
    },
    '2026-02-12': {
        'photo_time': '11:18',
        'photo_snow_cm': '0 (panele i podloze)',
        'photo_sky': 'sloneczny dzien',
        'photo_notes': 'luty referencyjny; brak sniegu na panelach i na podlozu; PV 9-16h ~16,6 kWh',
    },
    '2026-02-14': {
        'photo_time': '11:52',
        'photo_snow_cm': '0',
        'photo_sky': 'zachmurzenie (niebo niewidoczne; z kolorow na zdjeciu)',
        'photo_notes': 'brak sniegu; PV 9-16h ~7,6 kWh',
    },
    '2026-02-17': {
        'photo_time': '23:16',
        'photo_snow_cm': '~15 warstwa; czesc dachow cale, czesc do 2/3 powierzchni',
        'photo_sky': 'wieczor po zmroku',
        'photo_notes': 'foto wieczorne; mieszane pokrycie dachow; PV 17 II ~7,5 kWh w dzien (Typ B / granica)',
    },
    '2026-02-18': {
        'photo_time': '09:25',
        'photo_snow_cm': 'ogrodek (~10); 0 na panelach; pruszenie',
        'photo_sky': 'szare niebo, brak slonca',
        'photo_notes': 'Typ B: delikatny opad (pruszenie), panele czyste, snieg w ogrodzie; PV 9-16h ~5,4 kWh (niska produkcja = pochmurnosc, nie blokada paneli)',
    },
    '2026-02-20': {
        'photo_time': '17:46',
        'photo_snow_cm': '~5 (ogrodek); oznaki topnienia',
        'photo_sky': 'dachy niewidoczne; wieczor / po produkcji',
        'photo_notes': 'Typ B; pokrywa w ogrodzie ~5cm, topnienie; PV 9-16h ~17 kWh',
    },
    '2026-02-28': {
        'photo_time': '13:50',
        'photo_snow_cm': '0 na panelach',
        'photo_sky': 'bezchmurne niebo, slonce',
        'photo_notes': 'luty referencyjny (koniec miesiaca); PV 9-16h ~20,6 kWh',
    },
}

# Klasa ground truth (dzienna, z foto + PV — nie % chmur z kadru)
GROUND_TRUTH_CLASS: dict[str, str] = {
    '2025-11-21': 'snow_panel_block',
    '2025-11-23': 'snow_panel_block',
    '2025-11-24': 'snow_panel_block',
    '2025-11-27': 'snow_panel_block',
    '2025-11-28': 'snow_landscape',
    '2025-11-29': 'no_snow',
    '2025-12-04': 'partial_cloud',
    '2025-12-09': 'overcast_heavy',
    '2025-12-13': 'clear_sunny',
    '2025-12-15': 'fog',
    '2025-12-16': 'overcast_white',
    '2025-12-29': 'overcast_heavy',
    '2025-12-30': 'clear_sunny',
    '2025-12-31': 'snow_panel_block',
    '2026-01-01': 'snow_landscape',
    '2026-01-03': 'clear_sunny',
    '2026-01-09': 'snow_landscape',
    '2026-01-13': 'artifact',
    '2026-01-19': 'snow_landscape',
    '2026-01-20': 'snow_landscape',
    '2026-01-21': 'snow_landscape',
    '2026-01-22': 'snow_landscape',
    '2026-01-26': 'snow_landscape',
    '2026-01-27': 'snow_landscape',
    '2026-02-01': 'snow_landscape',
    '2026-02-03': 'clear_sunny',
    '2026-02-07': 'overcast_white',
    '2026-02-11': 'snow_landscape',
    '2026-02-12': 'clear_sunny',
    '2026-02-14': 'overcast_white',
    '2026-02-17': 'snow_landscape',
    '2026-02-18': 'snow_landscape',
    '2026-02-20': 'snow_landscape',
    '2026-02-28': 'clear_sunny',
}

# Grupy do oceny „bliskiego trafienia” (np. partial vs clear)
CLASS_GROUPS: dict[str, str] = {
    'snow_panel_block': 'snow_block',
    'snow_landscape': 'snow_landscape',
    'fog': 'fog',
    'clear_sunny': 'sky_good',
    'partial_cloud': 'sky_good',
    'overcast_white': 'sky_overcast',
    'overcast_heavy': 'sky_overcast',
    'no_snow': 'no_snow',
    'artifact': 'artifact',
    'evening_obs': 'evening_obs',
    'unknown': 'unknown',
}

# Współczynnik korekty prognozy PV (docelowo pod baterię)
PV_CORRECTION_FACTOR: dict[str, float] = {
    'snow_panel_block': 0.05,
    'snow_landscape': 1.0,
    'fog': 0.35,
    'clear_sunny': 1.0,
    'partial_cloud': 1.0,
    'overcast_white': 0.55,
    'overcast_heavy': 0.30,
    'no_snow': 0.85,
    'artifact': 1.0,
    'evening_obs': 1.0,
    'unknown': 1.0,
}


def parse_photo_validation(raw: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            day, label = part.split(':', 1)
        else:
            day, label = part, 'other'
        items.append((day.strip(), label.strip().lower()))
    return items


def ground_truth_for_day(day: str) -> str:
    return GROUND_TRUTH_CLASS.get(day, 'unknown')


def class_group(cls: str) -> str:
    return CLASS_GROUPS.get(cls, 'unknown')
