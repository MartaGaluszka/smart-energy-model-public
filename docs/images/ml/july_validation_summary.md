### Podsumowanie błędów (closeouty od lipca) — pogoda, hybryda, ENS

Metryka: **|APE| %** = `|actual − prognoza| / actual × 100`. Pogoda: średnie **cloud 6–20** z `weather_data` (ICON; od **02.09** primary = ensemble ICON+UKMO).

#### Kiedy błąd jest mniejszy / większy

| Typ dnia (cloud) | n | MAPE raw 5:00 | MAPE raw 12:00 | Dni |
|---|---:|---:|---:|---|
| słoneczny / mało chmur | 18 | 8.5% | 8.7% | 20.07, 26.07, 30.07, 04.08, 05.08, 06.08, 09.08, 12.08, 13.08, 14.08, 15.08, 27.08, 08.09, 09.09, 28.09, 29.09, 30.09, 02.10 |
| mieszany | 24 | 14.4% | 16.1% | 16.07, 17.07, 25.07, 28.07, 29.07, 31.07, 03.08, 08.08, 16.08, 20.08, 22.08, 23.08, 24.08, 28.08, 29.08, 30.08, 01.09, 02.09, 06.09, 15.09, 16.09, 19.09, 26.09, 27.09 |
| pochmurny / deszczowy | 39 | 25.2% | 26.3% | 14.07, 15.07, 18.07, 19.07, 21.07, 22.07, 23.07, 24.07, 27.07, 01.08, 02.08, 07.08, 10.08, 11.08, 17.08, 18.08, 19.08, 21.08, 25.08, 26.08, 31.08, 03.09, 04.09, 05.09, 07.09, 10.09, 11.09, 12.09, 13.09, 14.09, 17.09, 18.09, 20.09, 21.09, 22.09, 23.09, 24.09, 25.09, 01.10 |

- **Najtrafniejszy raw 5:00:** 30.07 (0.6% · słoneczny / mało chmur, cloud~31%, actual 33.5 kWh), 03.08 (0.7% · mieszany, cloud~48%, actual 33.5 kWh), 05.08 (1.2% · słoneczny / mało chmur, cloud~9%, actual 34.9 kWh)
- **Najgorszy raw 5:00:** 25.08 (149.8% · pochmurny / deszczowy, cloud~100%, actual 4.5 kWh), 24.07 (100.7% · pochmurny / deszczowy, cloud~86%, actual 10.7 kWh), 25.09 (79.2% · pochmurny / deszczowy, cloud~89%, actual 7.8 kWh)
- **Najgorszy raw 12:00:** 11.09 (174.8% · pochmurny / deszczowy, actual 3.1 kWh), 25.08 (152.7% · pochmurny / deszczowy, actual 4.5 kWh), 24.07 (79.7% · pochmurny / deszczowy, actual 10.7 kWh)
- **Rekord |APE| (cała seria 14.07–02.10):** **11.09** raw 12:00 **174.8%** (Fox **3.1** kWh vs prognoza midday **8.5** kWh) — wyżej niż dotychczasowy outlier **25.08** (152,7% midday). Accu reżim **CS4** OK; miss = poziom kWh, nie klasyfikacja.

- **Wzorzec:** na dniach **jasnych / wysokiej produkcji** raw bywa lekko **za niski** (NWP za chmurny vs Accu) — błąd umiarkowany w %, duży w kWh. Na dniach **słabych / burzowych** raw często **zawyża** — wtedy |APE| % eksploduje przy niskim Fox (**11.09** rekord **174,8%**; wcześniej klasa **25.08** ~153%). Od **02.09** primary to **ENS (ICON+UKMO)** — ten sam RF16, inna pogoda.

#### Kiedy hybryda dnia pomaga, a kiedy szkodzi

Porównanie **midday (12:00)**: hybryda = FoxESS na minione godziny + RF na resztę. „Pomaga/szkodzi” = różnica |APE| raw−hybryda ≥ **1 pp**.

- **Hybryda pomaga (12:00):** 18.07 (↓14.1 pp, pochmurny / deszczowy); 21.07 (↓18.9 pp, pochmurny / deszczowy); 23.07 (↓10.8 pp, pochmurny / deszczowy); 24.07 (↓55.0 pp, pochmurny / deszczowy)
- **Hybryda szkodzi (12:00):** 20.07 (↑13.2 pp, słoneczny / mało chmur); 22.07 (↑11.2 pp, pochmurny / deszczowy); 25.07 (↑16.7 pp, mieszany); 28.07 (↑11.3 pp, mieszany); 29.07 (↑13.4 pp, mieszany)
- **Remis / szum (<1 pp):** 14.07, 15.07, 16.07, 17.07, 19.07, 26.07, 27.07, 30.07, 31.07, 01.08, 02.08, 03.08, 04.08, 05.08, 06.08, 07.08, 08.08, 09.08, 10.08, 11.08, 12.08, 13.08, 14.08, 15.08, 16.08, 17.08, 18.08, 19.08, 20.08, 21.08, 22.08, 23.08, 24.08, 25.08, 26.08, 27.08, 28.08, 29.08, 30.08, 31.08, 01.09, 02.09, 03.09, 04.09, 05.09, 06.09, 07.09, 08.09, 09.09, 10.09, 11.09, 12.09, 13.09, 14.09, 15.09, 16.09, 17.09, 18.09, 19.09, 20.09, 21.09, 22.09, 23.09, 24.09, 25.09, 26.09, 27.09, 28.09, 29.09, 30.09, 01.10, 02.10

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
| 02.09–02.10 | era ENS primary (ICON+UKMO; gate 01.09, daily od 02.09) | 31 | 18.0% | 22.8% |
| 19.07–02.10 | **era PVE łącznie** (bez 14–18) | 76 | **17.7%** | **19.3%** |

_Zakres całość: 14.07–02.10 (81 closeoutów) · MAPE raw 5:00 = **18.1%** · MAPE raw 12:00 = **19.4%**._

#### Notatka odświeżenia 03.10.2026

- Zakres closeoutów: **14.07–02.10** (n=81). PNG + ten plik wygenerowane **03.10**.
- Linie na wykresie: **ICON** od **18.07** (wdrożenie 17.07 wieczór) · **kalibracja dual** od **26.07** · **ENS primary** od **02.09**.
- **ENS primary** od **02.09** (gate 01.09, pierwszy daily 5:00) — n=31 closeoutów · MAPE raw **18.0% / 22.8%**.
- Era dual ICON **27.07–01.09** (n=37): MAPE raw **15.6% / 15.8%**.
- Ostatnie closeouty (actual · |APE| raw 5:00): 25.09 **7.8** (raw 5:00 79.2%), 26.09 **30.2** (raw 5:00 43.3%), 27.09 **29.0** (raw 5:00 21.9%), 28.09 **31.8** (raw 5:00 13.1%), 29.09 **32.7** (raw 5:00 17.1%), 30.09 **31.6** (raw 5:00 14.0%), 01.10 **19.1** (raw 5:00 24.6%), 02.10 **31.3** (raw 5:00 14.3%).

#### Jak czytać PNG

- **`july_validation_plot.png`:** góra = kWh dnia (czarne = FoxESS; niebieski = raw 5:00; pomarańczowy = raw 12:00; fiolet/czerwień = hybryda). Dół = **|APE| %** — wysoki słupek to dzień, w którym model był daleko od faktu (zwykle słaby / deszczowy).
- **`production_validation_plot.png`:** góra = tylko **5:00** (raw ≈ hybryda, mało FoxESS). Dół = 5:00 i 12:00 razem. Tło od **02.09** = **ENS (ICON+UKMO)**.
- Dni **bez Porannej @05** (launchd / Mac spał) nie mają niebieskiej kropki 5:00 — oceniaj po **pomarańczowej** (12:00) lub **Popołudniowej** w app. **|APE| %** na bardzo niskim Fox (2–5 kWh) bywa ogromny przy błędzie kilku kWh — **11.09** to **najwyższy słupek |APE| w całej serii** (**174,8%** raw 12:00; wcześniejszy rekord **25.08** ~153%). Kontrast **12.09**: Fox **13,1** vs midday **13,47** (**−2,8%**).
