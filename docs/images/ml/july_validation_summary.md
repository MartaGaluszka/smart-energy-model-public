### Podsumowanie błędów (closeouty od lipca) — pogoda, hybryda, ENS

Metryka: **|APE| %** = `|actual − prognoza| / actual × 100`. Pogoda: średnie **cloud 6–20** z `weather_data` (ICON; od **02.09** primary = ensemble ICON+UKMO).

#### Kiedy błąd jest mniejszy / większy

| Typ dnia (cloud) | n | MAPE raw 5:00 | MAPE raw 12:00 | Dni |
|---|---:|---:|---:|---|
| słoneczny / mało chmur | 21 | 9.1% | 10.2% | 20.07, 26.07, 30.07, 04.08, 05.08, 06.08, 09.08, 12.08, 13.08, 14.08, 15.08, 27.08, 08.09, 09.09, 28.09, 29.09, 30.09, 02.10, 03.10, 05.10, 16.10 |
| mieszany | 29 | 17.5% | 17.3% | 16.07, 17.07, 25.07, 28.07, 29.07, 31.07, 03.08, 08.08, 16.08, 20.08, 22.08, 23.08, 24.08, 28.08, 29.08, 30.08, 01.09, 02.09, 06.09, 15.09, 16.09, 19.09, 26.09, 27.09, 04.10, 06.10, 07.10, 12.10, 13.10 |
| pochmurny / deszczowy | 45 | 26.7% | 25.5% | 14.07, 15.07, 18.07, 19.07, 21.07, 22.07, 23.07, 24.07, 27.07, 01.08, 02.08, 07.08, 10.08, 11.08, 17.08, 18.08, 19.08, 21.08, 25.08, 26.08, 31.08, 03.09, 04.09, 05.09, 07.09, 10.09, 11.09, 12.09, 13.09, 14.09, 17.09, 18.09, 20.09, 21.09, 22.09, 23.09, 24.09, 25.09, 01.10, 08.10, 09.10, 10.10, 11.10, 14.10, 15.10 |

- **Najtrafniejszy raw 5:00:** 08.10 (0.4% · pochmurny / deszczowy, cloud~77%, actual 18.8 kWh), 30.07 (0.6% · słoneczny / mało chmur, cloud~31%, actual 33.5 kWh), 03.08 (0.7% · mieszany, cloud~48%, actual 33.5 kWh)
- **Najgorszy raw 5:00:** 25.08 (149.8% · pochmurny / deszczowy, cloud~100%, actual 4.5 kWh), 14.10 (135.3% · pochmurny / deszczowy, cloud~94%, actual 6.6 kWh), 24.07 (100.7% · pochmurny / deszczowy, cloud~86%, actual 10.7 kWh)
- **Najgorszy raw 12:00:** 11.09 (174.8% · pochmurny / deszczowy, actual 3.1 kWh), 25.08 (152.7% · pochmurny / deszczowy, actual 4.5 kWh), 24.07 (79.7% · pochmurny / deszczowy, actual 10.7 kWh)
- **Rekord |APE| (cała seria 14.07–16.10):** **11.09** raw 12:00 **174.8%** (Fox **3.1** kWh vs prognoza midday **8.5** kWh) — wyżej niż dotychczasowy outlier **25.08** (152,7% midday). Accu reżim **CS4** OK; miss = poziom kWh, nie klasyfikacja.

- **Wzorzec:** na dniach **jasnych / wysokiej produkcji** raw bywa lekko **za niski** (NWP za chmurny vs Accu) — błąd umiarkowany w %, duży w kWh. Na dniach **słabych / burzowych** raw często **zawyża** — wtedy |APE| % eksploduje przy niskim Fox (**11.09** rekord **174,8%**; wcześniej klasa **25.08** ~153%). Od **02.09** primary to **ENS (ICON+UKMO)** — ten sam RF16, inna pogoda.

#### Tydzień po tygodniu — WAPE i bias (test live)

Raw 5:00 vs Fox, tygodnie pn–nd (od 03.08, min. 5 dni). **WAPE** = Σ|pred−Fox| / ΣFox (odporne na słabe dni, w przeciwieństwie do MAPE). **Bias** = Σ(pred−Fox) / ΣFox (minus = niedoszacowanie). Dni jasne = Fox ≥ 20 kWh. Progi OK / WATCH / ALARM: WAPE ≤15% / ≤22%, |bias| ≤8% / ≤12%, najgorszy dzień ≤25% / ≤40% — szczegóły i reguła „dwa tygodnie z rzędu”: `docs/NOTATKA_GATE_L30_CLOSEOUT.md`. **ICON solo** = shadow (ten sam RF16, pogoda tylko z ICON) liczony od 02.09 — porównuj z ENS tylko w tygodniach z pełnym n.

| Tydzień | n | Fox śr. [kWh] | WAPE | Bias | Bias dni jasnych | Najgorszy dzień | ICON solo WAPE | ICON bias | Ocena |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 03.08–09.08 | 7 | 30.4 | 6.3% | +1.4% | +0.6% (n=6) | 22% | — | — | **OK** · WAPE OK · bias OK · dzień OK |
| 10.08–16.08 | 7 | 33.2 | 7.8% | -6.4% | -6.4% (n=7) | 11% | — | — | **OK** · WAPE OK · bias OK · dzień OK |
| 17.08–23.08 | 7 | 23.6 | 14.6% | -0.9% | -6.3% (n=5) | 33% | — | — | **WATCH** · WAPE OK · bias OK · dzień WATCH |
| 24.08–30.08 | 7 | 26.5 | 20.0% | -12.7% | -16.8% (n=6) | 150% | — | — | **ALARM** · WAPE WATCH · bias ALARM · dzień ALARM |
| 31.08–06.09 | 7 | 25.4 | 11.7% | -6.1% | -6.1% (n=6) | 20% | 13.0% (n=5) | -8.0% | **OK** · WAPE OK · bias OK · dzień OK |
| 07.09–13.09 | 4 | 28.9 | 6.5% | -3.1% | -3.1% (n=4) | 9% | 9.4% (n=4) | -8.0% | **info (n<5)** |
| 14.09–20.09 | 7 | 23.9 | 13.0% | -12.0% | -13.9% (n=5) | 19% | 17.2% (n=7) | -15.9% | **WATCH** · WAPE OK · bias WATCH · dzień OK |
| 21.09–27.09 | 7 | 16.2 | 34.0% | -0.3% | -32.8% (n=2) | 79% | 25.8% (n=7) | -9.0% | **ALARM** · WAPE ALARM · bias OK · dzień ALARM |
| 28.09–04.10 | 7 | 29.5 | 13.9% | -13.9% | -12.8% (n=6) | 25% | 15.6% (n=7) | -15.6% | **ALARM** · WAPE OK · bias ALARM · dzień OK |
| 05.10–11.10 | 7 | 22.1 | 12.2% | -10.0% | -12.9% (n=4) | 28% | 19.1% (n=7) | -18.7% | **WATCH** · WAPE OK · bias WATCH · dzień WATCH |
| 12.10–18.10 | 5 | 14.0 | 45.0% | +29.3% | -20.0% (n=1) | 135% | 31.3% (n=5) | +4.4% | **ALARM** · WAPE ALARM · bias ALARM · dzień ALARM |

#### ENS vs dual ICON — korekta o miks pogody

Era ENS ma więcej dni pochmurnych (**53%** vs **35%** w erze dual), a na pochmurnych |APE| % jest zawyżone przez niski Fox — dlatego porównuj **te same typy dni** (różnica MAPE raw 5:00, ENS − dual): słoneczny / mało chmur: wyższy o 6.0 pp w erze ENS; mieszany: wyższy o 12.4 pp w erze ENS; pochmurny / deszczowy: niższy o 2.0 pp w erze ENS. Mała próba (n w komórkach) — to obserwacja, nie wniosek.

| Era | słoneczny / mało chmur (n · MAPE 5:00) | mieszany (n · MAPE 5:00) | pochmurny / deszczowy (n · MAPE 5:00) | udział dni pochmurnych |
|---|---:|---:|---:|---:|
| dual ICON 27.07–01.09 | 10 · 6.5% | 14 · 12.7% | 13 · 25.8% | 35% |
| ENS od 02.09 | 9 · 12.5% | 12 · 25.1% | 24 · 23.8% | 53% |

#### Kiedy hybryda dnia pomaga, a kiedy szkodzi

Porównanie **midday (12:00)**: hybryda = FoxESS na minione godziny + RF na resztę. „Pomaga/szkodzi” = różnica |APE| raw−hybryda ≥ **1 pp**.

- **Hybryda pomaga (12:00):** 18.07 (↓14.1 pp, pochmurny / deszczowy); 21.07 (↓18.9 pp, pochmurny / deszczowy); 23.07 (↓10.8 pp, pochmurny / deszczowy); 24.07 (↓55.0 pp, pochmurny / deszczowy)
- **Hybryda szkodzi (12:00):** 20.07 (↑13.2 pp, słoneczny / mało chmur); 22.07 (↑11.2 pp, pochmurny / deszczowy); 25.07 (↑16.7 pp, mieszany); 28.07 (↑11.3 pp, mieszany); 29.07 (↑13.4 pp, mieszany)
- **Remis / szum (<1 pp):** 14.07, 15.07, 16.07, 17.07, 19.07, 26.07, 27.07, 30.07, 31.07, 01.08, 02.08, 03.08, 04.08, 05.08, 06.08, 07.08, 08.08, 09.08, 10.08, 11.08, 12.08, 13.08, 14.08, 15.08, 16.08, 17.08, 18.08, 19.08, 20.08, 21.08, 22.08, 23.08, 24.08, 25.08, 26.08, 27.08, 28.08, 29.08, 30.08, 31.08, 01.09, 02.09, 03.09, 04.09, 05.09, 06.09, 07.09, 08.09, 09.09, 10.09, 11.09, 12.09, 13.09, 14.09, 15.09, 16.09, 17.09, 18.09, 19.09, 20.09, 21.09, 22.09, 23.09, 24.09, 25.09, 26.09, 27.09, 28.09, 29.09, 30.09, 01.10, 02.10, 03.10, 04.10, 05.10, 07.10, 08.10, 09.10, 10.10, 11.10, 12.10, 13.10, 14.10, 15.10, 16.10

- **O 5:00:** hybryda ≈ raw (pomaga 1 dni / szkodzi 1) — przed wschodem prawie nie ma FoxESS do podmiany.

**Reguła operacyjna (z tych closeoutów):**

- Hybryda **najczęściej pomaga**, gdy poranek modelu był **zawyżony** (typowo dni **słabe / pochmurne** — u nas dominanta wśród „pomaga”: **pochmurny / deszczowy**): FoxESS „ściąga” sumę w dół.
- Hybryda **szkodzi**, gdy raw był **za niski** na jasny dzień (u nas dominanta wśród „szkodzi”: **mieszany**), a KPI brało ścieżkę hybrydową zanim dzień się domknął — stąd reguła **outlook = model_raw** do późnego dnia.
- **Wniosek:** hybryda godzinowa jest OK do sugestii urządzeń; **suma dnia do oceny modelu** = raw (albo hybryda dopiero wieczorem).

#### MAPE po retreningach / wdrożeniach

Podział według **zmian logiki / targetu / cech** (nie każdy niedzielny odśwież wag). Weekly retreningi wchodzą w erę dual od 27.07. Od **02.09** primary NWP = ensemble ICON+UKMO (pionowa linia / tło na wykresie). Szczegóły: `docs/NOTATKA_RETRENINGI_I_WDROZENIA.md` · gate `docs/NOTATKA_TEST_ROUTING_28-31_08.md`.

| Okres closeoutów | Retraining / wdrożenie | n | MAPE raw 5:00 | MAPE raw 12:00 |
|---|---|---:|---:|---:|
| 14.07–18.07 | przed targetem PVE (skala mieszana; GPS/ICON 17.07) | 5 | 22.8% | 20.6% |
| 19.07–26.07 | po PVE 18.07 ~16:32 — przed dual 26.07 | 8 | 26.5% | 21.7% |
| 27.07–01.09 | era dual ICON primary (po 26.07; weekly = odświeżenie wag) | 37 | 15.6% | 15.8% |
| 02.09–16.10 | era ENS primary (ICON+UKMO; gate 01.09, daily od 02.09) | 45 | 21.7% | 22.5% |
| 19.07–16.10 | **era PVE łącznie** (bez 14–18) | 90 | **19.6%** | **19.6%** |

_Zakres całość: 14.07–16.10 (95 closeoutów) · MAPE raw 5:00 = **19.8%** · MAPE raw 12:00 = **19.7%**._

#### Notatka odświeżenia 17.10.2026

- Zakres closeoutów: **14.07–16.10** (n=95). PNG + ten plik wygenerowane **17.10**.
- Linie na wykresie: **ICON** od **18.07** (wdrożenie 17.07 wieczór) · **kalibracja dual** od **26.07** · **ENS primary** od **02.09**.
- **ENS primary** od **02.09** (gate 01.09, pierwszy daily 5:00) — n=45 closeoutów · MAPE raw **21.7% / 22.5%**.
- Era dual ICON **27.07–01.09** (n=37): MAPE raw **15.6% / 15.8%**.
- Ostatnie closeouty (actual · |APE| raw 5:00): 09.10 **18.1** (raw 5:00 9.3%), 10.10 **22.0** (raw 5:00 28.0%), 11.10 **16.0** (raw 5:00 24.8%), 12.10 **13.6** (raw 5:00 48.7%), 13.10 **10.2** (raw 5:00 84.9%), 14.10 **6.6** (raw 5:00 135.3%), 15.10 **12.0** (raw 5:00 14.7%), 16.10 **27.5** (raw 5:00 20.0%).

#### Jak czytać PNG

- **`july_validation_plot.png`:** góra = kWh dnia (czarne = FoxESS; niebieski = raw 5:00; pomarańczowy = raw 12:00; fiolet/czerwień = hybryda). Dół = **|APE| %** — wysoki słupek to dzień, w którym model był daleko od faktu (zwykle słaby / deszczowy).
- **`production_validation_plot.png`:** góra = tylko **5:00** (raw ≈ hybryda, mało FoxESS). Dół = 5:00 i 12:00 razem. Tło od **02.09** = **ENS (ICON+UKMO)**. Pomarańczowe linie pionowe = niedzielny weekly retrening (04:30); od **27.09** opis „REVIEW” (gate Δ MAE > +0,02), od **04.10** „+ L30” (dual report: shuffle + chronologiczny holdout 30 dni), **11.10** „XGB REVIEW” (RF/CS4 ACCEPT) — `docs/NOTATKA_RETRENINGI_I_WDROZENIA.md`, `docs/NOTATKA_GATE_DUAL_L30.md`.
- Dni **bez Porannej @05** (launchd / Mac spał) nie mają niebieskiej kropki 5:00 — oceniaj po **pomarańczowej** (12:00) lub **Popołudniowej** w app. **|APE| %** na bardzo niskim Fox (2–5 kWh) bywa ogromny przy błędzie kilku kWh — **11.09** to **najwyższy słupek |APE| w całej serii** (**174,8%** raw 12:00; wcześniejszy rekord **25.08** ~153%). Kontrast **12.09**: Fox **13,1** vs midday **13,47** (**−2,8%**).
