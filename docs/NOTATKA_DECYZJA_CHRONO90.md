# Decyzja: chrono-holdout 90 dni (zamiast 20%) jako raport nieblokujący

**Data:** 2026-11-09 · **Status:** wdrożone w kodzie, czeka na commit · **Powiązane:** [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)

## TL;DR

1. Raport „Chrono 20%” był liczony w środku niedzielnego treningu produkcyjnego. Błąd w raporcie mógł przerwać cały retrening (model zostałby stary, nie zepsuty). → **Raport opakowany w `try/except`.**
2. Okno 20% dawało wyższy MAE niż L30 (0,85 vs 0,59), ale to **głównie efekt sezonu**, nie gorszy model. Okno rosło też razem z danymi. → **Stałe okno 90 dni + WAPE + bias.**
3. Nic nie zmienia się w gate'ach L30 / shuffle, w locate/worker ani w capie. Raport pozostaje informacyjny.

## 1. Problem: raport mógł zablokować produkcję

Niedzielny skrypt (`mlops/train_dual_weekly.sh`) działa z `set -euo pipefail` i uczy po kolei: RF 16 (produkcja) → CS4 (shadow) → XGB+TS (shadow). Dodatkowy fit raportu chrono działał **przed** refitem produkcyjnym i zapisem `.joblib`.

| Scenariusz | Skutek (przed zmianą) |
|---|---|
| Wyjątek w raporcie (np. NaN w danych, błąd fit) | Przerwanie kroku [1/3], CS4 i XGB+TS się nie uruchamiają, `.joblib` nie jest odświeżony |
| Model po przerwaniu | **Stary, nie zepsuty** — prognoza baterii działa, ale tydzień bez retreningu |

Wniosek: raport informacyjny nie może mieć możliwości zablokowania treningu produkcyjnego. Koszt zabezpieczenia jest minimalny.

**Decyzja:** `evaluate_chrono90_safe` łapie dowolny wyjątek, wypisuje ostrzeżenie `⚠️ Chrono 90d pominięty (raport, nie gate)` i zwraca pusty wynik (`None`) — tak jak przy „za mało dni”. Trening, gate'y L30 i shuffle idą dalej.

## 2. Problem: czy okno 20% ma sens, skoro błąd jest większy?

Sprawdzone na danych (RF 16, okno 2025-06-01 → 2026-11-08, model sprawdzony na ostatnich dniach po treningu na wcześniejszych).

| | L30 (10.10–08.11) | Chrono 20% (29.07–08.11) |
|---|---|---|
| Dni testowe | 30 | 103 |
| MAE (kWh/h) | 0,587 | 0,848 |
| Średnia produkcja w oknie (kWh/h) | 1,44 | 1,96 |
| **Błąd względny (WAPE)** | **0,409** | **0,432** |
| Bias (pred − real, kWh/h) | −0,09 | −0,22 |
| Dni treningowe | 487 | 414 |

Wnioski:

- **Większy MAE to głównie efekt poziomu.** Produkcja w oknie 20% jest o ~36% wyższa (sierpień, wrzesień), więc bezwzględny błąd rośnie. Po przeliczeniu na procent produkcji oba okna są prawie równe (43% vs 41%).
- **Prawdziwy koszt „starszego” modelu jest mały, ale realny.** Model z chrono 20% oceniony na tym samym oknie L30 daje 0,651 zamiast 0,587 (+11%) — tyle kosztuje brak ostatnich ~100 dni treningu.
- **Bias jest istotniejszy niż MAE.** Model bez świeżych danych zaniża produkcję o ~0,2 kWh/h (we wrześniu −0,29). Dla planowania baterii to ważny sygnał, którego MAE nie pokazuje.
- **Porównywanie surowego MAE między oknami jest nieuczciwe**, więc progi soft gate L30 (0,75–1,00) nie mogą być stosowane do chrono.

## 3. Rozważone opcje

| Opcja | Za | Przeciw | Decyzja |
|---|---|---|---|
| **A. Zostawić 20%** (tylko z `try/except`) | Zero dodatkowej pracy, 103 dni to mniejsza wariancja niż 30 | Okno rośnie z danymi (dziś 103 dni, przy ~700 dniach historii ok. 140) → tydzień do tygodnia nieporównywalny; MAE zależny od sezonu; brak informacji o biasie | odrzucona |
| **B. Usunąć raport** | Mniej kodu | Tracimy sygnał o dryfie i zaniżaniu; jedyny chrono-holdout to 30 dni jesienią | odrzucona |
| **C. Stałe 90 dni + WAPE + bias** | Stałe okno → czytelny trend; wiele reżimów pogodowych; WAPE porównywalny między sezonami; bias widzi zaniżanie; praktycznie jedna linia (istniejąca `chronological_l30_masks(hold_days=90)`) | Okno nadal obejmuje część lata (ale stała długość to nie szkodzi trendowi) | **wybrana** |
| D. Walk-forward 3×30 dni | Każdy blok trenowany na „wszystkim przed” | 3 fity zamiast 1, brak wyraźnej przewagi nad C | odrzucona (na razie) |

Dodatkowy argument za zmianą **teraz**: kolumny `chrono*` jeszcze nigdy nie trafiły do historii (`weekly_dual_metrics.csv` nie ma ich w nagłówku; pierwszy wpis powstanie w niedzielę 15.11). Przemianowanie na `chrono90_*` nic więc nie psuje; później byłoby to niepotrzebne zamieszanie.

## 4. Co dokładnie wdrożono

- `src/models/weekly_dual_metrics.py`: `evaluate_holdout_pipeline` zwraca też `wape` i `bias`; nowy `evaluate_chrono90_safe` (stałe `CHRONO90_HOLD_DAYS = 90`, `try/except`); `print_dual_report` dodaje linię WAPE / bias.
- `scripts/train/train_hourly_model_tuning.py`, `scripts/train/train_xgb_ts_shadow.py`: nowy wrapper, kolumny `chrono90_*` (m.in. `chrono90_wape`, `chrono90_bias`) w CSV i metadata.
- `scripts/train/weekly_dual_gate_report.py`: tabela zbiorcza pokazuje `chrono90 MAE (WAPE %, bias)`.
- `tests/test_weekly_dual_metrics.py`: 15 testów (wartości `wape`/`bias`, za krótka historia, NaN, brak kolumny `day`).

**Bez zmian:** gate'y L30 i shuffle (`hard_reject=False` dla L30), produkcyjny refit na pełnym oknie expanding, locate/worker, cap (zostaje w shadow min. 2 tygodnie; przed włączeniem do aplikacji osobny test planu baterii).

## 5. Weryfikacja

- Testy: 15/15 zielone.
- Próbny przebieg na **kopii** repo i bazy, bez zapisu `.joblib` (samo `--no-save` nie wystarcza: skrypt i tak dopisuje do `weekly_dual_metrics.csv`, co przesunęłoby bazę shuffle gate). Prawdziwe pliki niezmienione.
- Wynik próbny (okno 11.08 → 08.11):

| Model | Chrono 90d MAE | WAPE | Bias (kWh/h) | Shuffle gate |
|---|---|---|---|---|
| RF 16 (produkcja) | 0,801 | 41,8% | −0,214 (zaniża) | ACCEPT (Δ +0,011) |
| XGB+TS (shadow) | 0,777 | 40,5% | −0,269 (zaniża) | ACCEPT (Δ +0,010) |

- Nie sprawdzone osobno: CS4 (ta sama ścieżka kodu co RF 16); ścieżka błędu pokryta testem jednostkowym, bez pełnego treningu na celowo zepsutych danych.

## 6. Ograniczenia i co dalej

- Raport jest **informacyjny, bez progów**. Obserwacja min. 2 tygodnie (jak cap); dopiero potem rozważyć próg na `bias`.
- Okno 90 dni nadal zawiera sezonowość (lato → jesień), więc interpretować trend `wape` i `bias`, a nie pojedynczą wartość MAE.
- Bias ujemny oznacza ostrożniejszą prognozę produkcji. Przy planie baterii (reguła push 22:00 itd.) warto sprawdzić, czy zaniżanie nie przesuwa decyzji w stronę niepotrzebnego ładowania z sieci — **to osobne zadanie**, nie część tej zmiany.
- Po weekly 15.11 sprawdzić w logu: linia `Chrono 90d MAE/WAPE`, brak `⚠️ Chrono 90d pominięty`, nowe kolumny `chrono90_*` w `data/processed/weekly_dual_metrics.csv`.
