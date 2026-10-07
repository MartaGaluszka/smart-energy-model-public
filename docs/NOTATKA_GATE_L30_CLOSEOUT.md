# Kryteria: closeout tygodniowy (live) i przejście L30 na twardy gate

**Data ustalenia:** 2026-10-05 · **Status:** propozycja robocza (do rewizji po 6 tygodniach i po wejściu w zimę)  
**Kontekst:** dual report (shuffle + L30 soft) — [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md) · pierwszy pełny weekly z dual: [`NOTATKA_WEEKLY_2026-10-04.md`](NOTATKA_WEEKLY_2026-10-04.md)

Trzy testy jakości modelu PV:

| Test | Podział | Rola dziś |
|------|---------|-----------|
| 1. Shuffle 80/20 po dniach | losowe 20% dni | **twardy gate** (REVIEW jeśli Δ > +0,02 vs poprzedni weekly) |
| 2. L30 chronologiczny | ostatnie 30 dni do `train_end` | **soft** (INFO / WATCH, `hard_reject=False`) |
| 3. Closeout live | prognoza @05 vs Fox | **kryterium tygodniowe** (poniżej) |

---

## Test 3 — closeout tygodniowy (Fox vs prognoza)

**Metryka główna: WAPE** = Σ\|pred − Fox\| / ΣFox (nie MAPE — jeden słaby dzień psuje średnią procentową; np. tydzień 24.08: MAPE 36%, WAPE 20%).

**Wejście:** prognoza `daily` @05 (lead 0) z `forecast_history.csv`, Fox = `MAX(total_kwh)` z `foxess_report_daily`; minimum **5 dni** z kompletnym Fox w tygodniu (pn–nd). Oceniamy osobno: ENS primary, CS4 i XGB (shadow), Accu (paper — tylko repo prywatne).

| Metryka | OK | WATCH | ALARM |
|---------|----|-------|-------|
| WAPE tygodnia | ≤ 15% | 15–22% | > 22% |
| Bias tygodnia, Σ(pred−Fox)/ΣFox | \|b\| ≤ 8% | 8–12% | > 12% |
| Najgorszy dzień \|błąd\| | ≤ 25% | 25–40% | > 40% |

**Zasady:**

1. **Alarm sumaryczny:** ALARM w WAPE, albo WATCH/ALARM w bias lub WAPE **dwa tygodnie z rzędu**. Pierwsze zdarzenie = notatka; dopiero drugie z rzędu = przegląd.
2. **Bias osobno** dla dni słonecznych (Fox ≥ 20 kWh) i pochmurnych (< 20). Systematyczne niedoszacowanie słońca ≠ pudło na zachmurzeniu.
3. **Baseline:** WAPE modelu ma być niższe niż naiwnej prognozy „tyle co wczoraj" (Fox z dnia poprzedniego). Jeśli nie — model nie wnosi nic ponad persistence.
4. Wynik zapisujemy w notatce weekly (tabela dzień po dniu + WAPE / bias / najgorszy dzień).

### Kalibracja progów (historia 03.08–04.10, ENS @05)

| Tydzień | n | Fox śr. | WAPE | Bias | Najgorszy | Bias słońce | WAPE naiwna |
|---------|--:|--------:|-----:|-----:|----------:|------------:|------------:|
| 03.08–09.08 | 7 | 30,4 | 6,3% | +1,4% | 22% | +0,6% | 30,0% |
| 10.08–16.08 | 7 | 33,2 | 7,8% | −6,4% | 11% | −6,4% | 14,7% |
| 17.08–23.08 | 7 | 23,6 | 14,6% | −0,9% | 33% | −6,3% | 37,1% |
| 24.08–30.08 | 7 | 26,5 | 20,0% | −12,7% | 150% | −16,8% | 48,1% |
| 31.08–06.09 | 7 | 25,4 | 11,7% | −6,1% | 20% | −6,1% | 19,3% |
| 07.09–13.09 | 4 | 28,9 | 6,5% | −3,1% | 9% | −3,1% | 18,9% |
| 14.09–20.09 | 7 | 23,9 | 13,0% | −12,0% | 19% | −13,9% | 52,7% |
| 21.09–27.09 | 7 | 16,2 | 34,0% | −0,3% | 79% | −32,8% (n=2) | 48,4% |
| **28.09–04.10** | 7 | 29,5 | **13,9%** | **−13,9%** | 25% | **−12,8%** | 15,1% |

Mediana WAPE ≈ 13%, najlepszy tydzień ≈ 6%, najgorszy 34% (tydzień o bardzo małej produkcji). Tydzień 07.09 ma tylko 4 dni (poniżej minimum 5 — wiersz informacyjny).

**Stan na 05.10:** ostatni tydzień → WAPE OK, **bias ALARM (−13,9%)**, najgorszy dzień WATCH (−25%), przewaga nad naiwną niewielka (13,9% vs 15,1%). Poprzedni tydzień (21–27.09) miał bias −0,3% (WAPE 34% = ALARM, ale przy bardzo małej produkcji), więc bias nie jest jeszcze „dwa tygodnie z rzędu" — **pierwsze zdarzenie = tylko notatka**. Jeśli tydzień 05–11.10 nadal ma \|bias\| > 8% → **przegląd** (nie auto-rollback; patrz niżej). Wcześniej podobny wzorzec: 14–20.09 bias −12,0%.

---

## L30: przejście z INFO na twardy gate

Wszystkie cztery warunki naraz:

1. **Historia:** co najmniej **6** tygodniowych punktów L30 dla danego modelu. Stan na 05.10: RF16 — 2 (27.09, 04.10), CS4 i XGB+TS — 1 (04.10). Najwcześniej ok. **08.11**.
2. **Kalibracja progu z danych**, nie z zakresu 0,75–1,00: próg WATCH = **P90 historii L30** (albo mediana + 2×MAD). Zakres 0,75–1,00 był oszacowany na jesień i zimą się przesunie.
3. **Predykcyjność:** korelacja Spearmana L30 (daily MAE) z WAPE closeoutu z kolejnego tygodnia ≥ **0,5**. Jeśli L30 nie przewiduje live — zostaje informacyjny.
4. **Reguła odrzucenia wielosygnałowa:** rollback wag tylko gdy jednocześnie: L30 > próg P90 **i** shuffle gate = REVIEW **i** closeout = WATCH/ALARM. Rollback **ręczny** do poprzedniego `.joblib`; pojedyncza metryka nigdy nie odrzuca wag.

**Monitor stabilności:** L30 − shuffle (dziś RF16: 0,808 − 0,671 = 0,137 kWh/h). Wartość > **0,25** = sygnał, że model uczy się „sąsiednich dni", nie zjawiska (XGB+TS: różnica 0,196 — pod progiem).

**Rewizja progów:** po wejściu w zimę (grudzień–styczeń) przeliczyć — MAE w kWh/h spadnie przez krótki dzień.

---

## Źródło pogody: kiedy wracać z ENS do ICON solo

ICON solo liczy się jako shadow (ten sam RF16, pogoda tylko z ICON) od 02.09 i jest widoczny na `production_validation_plot.png` (cienka linia) oraz w tabeli tygodniowej.

**Stan na 05.10 (30 par dni 02.09–04.10):** ENS MAE 3,64 kWh · WAPE 15,1% · bias −7,7%; ICON solo 3,89 · 16,1% · −12,2%. ENS bliżej Fox w 12 dniach, ICON w 6, remis w 12; różnica nieistotna statystycznie (95% CI −0,46…+0,94 kWh). ICON ma lepszy MAPE tylko dzięki słabym dniom (Fox < 15 kWh: bias ENS +31%, ICON +12%).

**Wracamy do ICON solo, gdy:** ICON ma niższy WAPE niż ENS w **4 kolejnych tygodniach** (każdy ≥ 5 dni z pełną parą) **albo** przedział ufności średniej różnicy błędu bezwzględnego leży w całości po stronie ICON. Do tego czasu ENS = primary.

Niedoszacowanie dni jasnych jest wspólne dla obu źródeł → przyczyna w modelu, nie w API ([`NOTATKA_BIAS_JASNE_DNI_2026-10-05.md`](NOTATKA_BIAS_JASNE_DNI_2026-10-05.md)).

---

## L30 vs shuffle vs live (stan na 07.10)

Trening 04.10 (`train_end` 03.10), okno L30: **04.09 → 03.10**. Live liczone z `forecast_validation.csv` i pierwszego runu dnia w `forecast_history.csv` (@05 vs Fox).

### Offline: shuffle vs L30

| Model | MAE godz. shuffle | MAE godz. L30 | Różnica | MAE dzienne shuffle | MAE dzienne L30 |
|-------|------------------:|--------------:|--------:|--------------------:|----------------:|
| RF16 (primary) | 0,671 | 0,807 | +0,136 | 3,54 | 3,71 |
| CS4 | 0,673 | 0,794 | +0,121 | 3,50 | **3,46** |
| XGB+TS | **0,646** | 0,842 | +0,196 | 3,37 | 3,85 |

Bez tasowania każdy model wypada gorzej godzinowo, a kolejność się zmienia: shuffle daje XGB+TS najlepszy, L30 daje CS4 najlepszy, a XGB+TS najgorszy. Wszystkie różnice są poniżej progu **0,25**.

### Live w oknie L30 (28 dni z Fox) vs offline

| Model | Live MAE dzienne | WAPE | L30 offline | Shuffle offline |
|-------|-----------------:|-----:|------------:|----------------:|
| RF16 (ENS) | **3,6** | 15,8% | 3,71 | 3,54 |
| RF16 (ICON solo) | 3,9 | 17,1% | 3,71 | 3,54 |
| CS4 | 4,4 | 19,4% | 3,46 | 3,50 |
| XGB+TS | 4,2 | 18,6% | 3,85 | 3,37 |

- RF16 live pokrywa się z L30 i shuffle (3,6–3,9 vs 3,5–3,7).
- CS4 i XGB+TS są live o ok. **0,4–0,9 kWh/dzień** gorsze niż w obu testach offline. L30 wskazał CS4 jako najlepszy, live go nie potwierdza.
- Hipoteza (niesprawdzona): testy offline liczą się na pogodzie z archiwum, live na prognozie.
- Warunek 3 twardego gate (korelacja Spearmana L30 z live ≥ 0,5) jest nie do sprawdzenia przy 2 punktach L30. Ten przykład pokazuje, że L30 nie przewidział kolejności modeli.

### Live po retrainie 04.10 (04–06.10, n = 3)

| | WAPE | Bias |
|--|-----:|-----:|
| ENS (primary) | **9,0%** | −9,0% |
| CS4 | 14,3% | −14,3% |
| XGB+TS | 18,5% | −18,5% |
| ICON solo | 15,0% | −15,0% |
| ENS, tydzień 28.09–04.10 (dla porównania) | 13,9% | −13,9% |

- Tylko 3 dni (minimum z reguły: **5**), więc to obserwacja, nie ocena tygodnia.
- 04.10 i 05.10 wszystkie modele **−4…−8%**. Różnica pojawia się 06.10: ENS **−17%**, CS4 **−34%**, ICON **−38%**, XGB+TS **−44%**.
- Bias jest ujemny w każdym tygodniu i modelu (znany undershoot jasnych dni). Retrain go nie zmienił.

Wniosek: primary (RF16 + ENS) potwierdza się live. Metryki offline shadow modeli są zbyt optymistyczne. Twardy gate nadal nie ma podstaw (warunek 1: 2 z 6 punktów).

Tygodniowe WAPE przeliczone z danych różni się od tabeli wyżej w dwóch tygodniach: **07.09** (n = 5 zamiast 4) i **14.09** (12,5% zamiast 13,0%). Pozostałe tygodnie są zgodne.

---

## Harmonogram

| Kiedy | Co |
|-------|----|
| co niedzielę (weekly) | dopisać L30 + tabelę WAPE / bias do `NOTATKA_WEEKLY_*.md` |
| 11.10, 18.10, 25.10, 01.11 | kolejne punkty L30 (RF16: 3.–6.) |
| ~08.11 | pierwsza ocena warunków 1–3; decyzja o twardym gate |
| grudzień / styczeń | przeliczenie progów dla zimy |

Powiązane: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · [`NOTATKA_RETRENINGI_I_WDROZENIA.md`](NOTATKA_RETRENINGI_I_WDROZENIA.md)
