# Notatka — niedoszacowanie na dniach jasnych (diagnoza 05.10.2026)

**Pytanie:** dlaczego raw 5:00 niedoszacowuje dni jasnych (Fox ≥ 25 kWh) o ok. −14% (ENS) / −16% (ICON solo)?  
**Skrypty:** [`scripts/analysis/diagnose_sunny_bias.py`](../scripts/analysis/diagnose_sunny_bias.py) · [`scripts/analysis/experiment_panel_geometry_oos.py`](../scripts/analysis/experiment_panel_geometry_oos.py)  
**Status:** diagnoza + eksperymenty offline. **Nic nie zmieniono w produkcji** ani w `models/`.

---

## Werdykt (1 zdanie)

> Błąd siedzi w **modelu (kształt dnia godzina po godzinie)**, nie w źródle pogody: nawet z pogodą z archiwum (czyli „idealną prognozą") model niedoszacowuje jasne dni o **−11% (in-sample) / −16,5% (OOS)**, a prognoza ENS ma radiację **wyższą** niż archiwum (+7,1%), nie niższą.

---

## 1. To nie NWP

Dni jasne od 02.09 (n=17):

| | Wynik |
|--|------:|
| Bias modelu z **pogodą z archiwum**, in-sample (model produkcyjny) | **−11,0%** |
| Bias modelu z pogodą z archiwum, **OOS** (trening tylko < 01.09) | **−16,5%** |
| Radiacja dnia: prognoza ENS vs archiwum | **+7,1%** |
| Radiacja dnia: ICON vs archiwum | +2,5% |
| Zachmurzenie śr.: ENS / ICON / archiwum | 39% / 44% / 50% |

Prognoza jest „słoneczniejsza" niż archiwum, a mimo to prognoza PV jest za niska → przyczyna po stronie modelu. (Uwaga: `weather_data` trzyma ostatnio zapisaną prognozę dla godziny, nie snapshot @05.)

Ten sam wzorzec w ICON solo (−16,5% na dniach ≥ 25 kWh), więc **powrót do ICON tego nie naprawi**.

## 2. Gdzie w ciągu dnia (dni jasne od 02.09, OOS)

| Godzina | Fox [kWh/h] | Model | Błąd |
|--------:|------:|------:|-----:|
| 6–8 | 0,1 / 0,6 / 1,8 | 1,1 / 1,9 / 2,5 | **+44% … +1000%** |
| 10 | 3,8 | 3,6 | −5% |
| 12 | 4,4 | 3,5 | −20% |
| 14 | 3,5 | 2,0 | **−45%** |
| 16 | 1,7 | 0,6 | **−64%** |

Model „startuje" za wcześnie i gaśnie za wcześnie: dzwon produkcji jest przesunięty względem rzeczywistego (szczyt Fox ~12–13h). Ten sam kształt widać też na czystym dniu letnim (05.08: plateau ~4,0 kWh/h do 13h, potem 3,3 / 2,6 / 1,5 vs Fox 3,8 / 3,6 / 2,3) — jesienią tylko jest większy.

## 3. Sezonowość

Bias na dniach jasnych, model produkcyjny z archiwalną pogodą (in-sample):

| 2025‑07 | 2025‑08 | 2025‑09 | 2026‑02 | 2026‑03 | 2026‑04 | 2026‑05 | 2026‑06 | 2026‑07 | 2026‑08 | 2026‑09 | 2026‑10 |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| −7,5% | −5,4% | −7,5% | −17,1% | −13,5% | −12,5% | −5,5% | −12,3% | −4,0% | −4,0% | −11,4% | −7,8% |

Bias jest **chroniczny** (−4% … −17%), większy w miesiącach niskiego słońca (II–IV, IX–X), choć czerwiec 2026 też −12%. Sprawność Fox na kWh/m² radiacji poziomej na dniach jasnych rośnie z ok. **5,3–5,7** (sierpień) do **8,5** (koniec września) — panele pochylone łapią więcej niskiego słońca niż pomiar poziomy, a model ma tylko radiację poziomą.

## 4. Eksperymenty offline (trening < 01.09, test od 01.09 = 34 dni, 18 jasnych, pogoda z archiwum)

| Wariant | MAE godz. | WAPE dnia | Bias dnia | Bias jasne | 14–16h jasne | 6–8h jasne |
|---------|----------:|----------:|----------:|-----------:|-------------:|-----------:|
| Baseline (16 cech produkcji) | 0,81 | 15,9% | −11,7% | −16,0% | −51% | +95% |
| + geometria paneli (tilt 35°, az 180°) | 0,79 | 14,7% | −9,5% | −14,0% | −49% | +96% |
| + geometria, az 200° / 220° | 0,81 | 14,8% / 15,5% | −10,1% / −11,2% | −14,3% / −15,4% | −49% / −51% | +101% / +99% |
| RF mniej regularyzowany (depth 10–∞) | 0,83–0,86 | 14,0–14,4% | −11,3 … −11,6% | −14,6 … −14,8% | −53 … −55% | +106 … +115% |
| **+ radiacja i chmury z NASTĘPNEJ godziny** | 0,79 | **11,7%** | **−6,8%** | **−10,3%** | −43% | +118% |

- **Geometria paneli** (przygotowana w `src/features/panel_geometry.py`, wyłączona) pomaga niewiele i nie naprawia kształtu dnia. Inne azymuty nie są lepsze.
- **Regularyzacja** (min‑gap) nie jest przyczyną — luźniejszy RF poprawia WAPE, ale pogarsza MAE godzinowy i nie rusza kształtu.
- **Cechy z następnej godziny** dają największy zysk (WAPE 15,9% → 11,7%, bias jasnych −16% → −10%).

## 5. Hipoteza robocza (do potwierdzenia)

Open-Meteo podaje radiację jako **średnią z poprzedniej godziny**, a target to przyrost licznika w danej godzinie. Jeśli pogoda w wierszu `hour = h` opisuje godzinę `h−1`, to model dostaje cechy opóźnione o ~1 h względem produkcji i nadrabia to cechami `hour`, `hours_since_sunrise`, `sun_position` — stąd przesunięty dzwon. Wynik eksperymentu jest zgodny z tą hipotezą, ale **nie sprawdzono jeszcze znaczników czasu w loaderze** (`load_weather_hourly`) ani konwencji etykiet godzin w `load_hourly_pv_dynamic`.

## 6. Ograniczenia

- Jeden holdout (34 dni, 18 jasnych); test na dniach, których model nie widział — to trudny scenariusz (ekstrapolacja do niższego słońca), po retreningu tygodniowym bias spada (in-sample −11%).
- Pogoda z archiwum, nie z prognozy: w produkcji dochodzi błąd NWP.
- Wariant „następna godzina" wybrany po obejrzeniu profilu godzinowego — wymaga walidacji na L30 i rolling origin zanim cokolwiek trafi do produkcji.

## 7. Proponowane kroki (bez zmian produkcyjnych)

1. **Sprawdzić wyrównanie czasu** radiacja ↔ PV w loaderze i na surowych danych (1–2 dni jasnych, wiersz po wierszu).
2. Jeśli potwierdzone: cecha `radiation/cloud` z następnej godziny (albo naprawa wyrównania) jako **shadow** → dual report (shuffle + L30) → closeouty live ≥ 2 tygodnie.
3. Dopiero wtedy decyzja o primary; geometrię paneli odłożyć (niski zysk).
4. Monitorować w tabeli tygodniowej bias dni jasnych ([`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)).

Powiązane: [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md) · [`images/ml/july_validation_summary.md`](images/ml/july_validation_summary.md) · [`CHANGELOG_ML.md`](CHANGELOG_ML.md) § geometria paneli
