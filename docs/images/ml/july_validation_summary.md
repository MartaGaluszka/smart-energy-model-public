### Podsumowanie błędów (lipiec) — pogoda i hybryda

Metryka: **|APE| %** = `|actual − prognoza| / actual × 100`. Pogoda: średnie **cloud ICON 6–20** z `weather_data`.

#### Kiedy błąd jest mniejszy / większy

| Typ dnia (cloud) | n | MAPE raw 5:00 | MAPE raw 12:00 | Dni |
|---|---:|---:|---:|---|
| słoneczny / mało chmur | 12 | 6.5% | 6.0% | 20.07, 26.07, 30.07, 04.08, 05.08, 06.08, 09.08, 12.08, 13.08, 14.08, 15.08, 27.08 |
| mieszany | 15 | 12.0% | 15.0% | 16.07, 17.07, 25.07, 28.07, 29.07, 31.07, 03.08, 08.08, 16.08, 20.08, 22.08, 23.08, 24.08, 28.08, 29.08 |
| pochmurny / deszczowy | 20 | 30.1% | 26.1% | 14.07, 15.07, 18.07, 19.07, 21.07, 22.07, 23.07, 24.07, 27.07, 01.08, 02.08, 07.08, 10.08, 11.08, 17.08, 18.08, 19.08, 21.08, 25.08, 26.08 |

- **Najtrafniejszy raw 5:00:** 30.07 (0.6% · słoneczny / mało chmur, cloud~31%, actual 33.5 kWh), 03.08 (0.7% · mieszany, cloud~48%, actual 33.5 kWh), 05.08 (1.2% · słoneczny / mało chmur, cloud~9%, actual 34.9 kWh)
- **Najgorszy raw 5:00:** 25.08 (149.8% · pochmurny / deszczowy, cloud~100%, actual 4.5 kWh), 24.07 (100.7% · pochmurny / deszczowy, cloud~86%, actual 10.7 kWh), 15.07 (59.5% · pochmurny / deszczowy, cloud~94%, actual 10.9 kWh)

- **Wzorzec:** na dniach **jasnych / wysokiej produkcji** raw bywa lekko **za niski** (ICON za chmurny vs Accu) — błąd umiarkowany w %, duży w kWh. Na dniach **słabych / burzowych** raw często **zawyża** — wtedy |APE| % bywa największy.

#### Kiedy hybryda dnia pomaga, a kiedy szkodzi

Porównanie **midday (12:00)**: hybryda = FoxESS na minione godziny + RF na resztę. „Pomaga/szkodzi” = różnica |APE| raw−hybryda ≥ **1 pp**.

- **Hybryda pomaga (12:00):** 18.07 (↓14.1 pp, pochmurny / deszczowy); 21.07 (↓18.9 pp, pochmurny / deszczowy); 23.07 (↓10.8 pp, pochmurny / deszczowy); 24.07 (↓55.0 pp, pochmurny / deszczowy)
- **Hybryda szkodzi (12:00):** 20.07 (↑13.2 pp, słoneczny / mało chmur); 22.07 (↑11.2 pp, pochmurny / deszczowy); 25.07 (↑16.7 pp, mieszany); 28.07 (↑11.3 pp, mieszany); 29.07 (↑13.4 pp, mieszany)
- **Remis / szum (<1 pp):** 14.07, 15.07, 16.07, 17.07, 19.07, 26.07, 27.07, 30.07, 31.07, 01.08, 02.08, 03.08, 04.08, 05.08, 06.08, 07.08, 08.08, 09.08, 10.08, 11.08, 12.08, 13.08, 14.08, 15.08, 16.08, 17.08, 18.08, 19.08, 20.08, 21.08, 22.08, 23.08, 24.08, 25.08, 26.08, 27.08, 28.08, 29.08

- **O 5:00:** hybryda ≈ raw (pomaga 1 dni / szkodzi 1) — przed wschodem prawie nie ma FoxESS do podmiany.

**Reguła operacyjna (z tych closeoutów):**

- Hybryda **najczęściej pomaga**, gdy poranek modelu był **zawyżony** (typowo dni **słabe / pochmurne** — u nas dominanta wśród „pomaga”: **pochmurny / deszczowy**): FoxESS „ściąga” sumę w dół.
- Hybryda **szkodzi**, gdy raw był **za niski** na jasny dzień (u nas dominanta wśród „szkodzi”: **mieszany**), a KPI brało ścieżkę hybrydową zanim dzień się domknął — stąd reguła **outlook = model_raw** do późnego dnia.
- **Wniosek:** hybryda godzinowa jest OK do sugestii urządzeń; **suma dnia do oceny modelu** = raw (albo hybryda dopiero wieczorem).

#### MAPE po retreningach / wdrożeniach

Podział według **zmian logiki / targetu / cech** (nie każdy niedzielny odśwież wag). Weekly retreningi wchodzą w erę dual od 27.07 (do ostatniego closeoutu). Szczegóły: `docs/NOTATKA_RETRENINGI_LIPIEC_2026.md`.

| Okres closeoutów | Retraining / wdrożenie | n | MAPE raw 5:00 | MAPE raw 12:00 |
|---|---|---:|---:|---:|
| 14.07–18.07 | przed targetem PVE (skala mieszana; GPS/ICON 17.07) | 5 | 22.8% | 20.6% |
| 19.07–26.07 | po PVE 18.07 ~16:32 — przed dual 26.07 | 8 | 26.5% | 21.7% |
| 27.07–29.08 | era produkcyjna dual (po 26.07; weekly = odświeżenie wag; do ostatniego closeoutu) | 34 | 15.7% | 15.9% |
| 19.07–29.08 | **era PVE łącznie** (bez 14–18) | 42 | **17.8%** | **17.0%** |

_Zakres całość: 14.07–29.08 (47 closeoutów) · MAPE raw 5:00 = **18.3%** · MAPE raw 12:00 = **17.4%**._

#### Notatka odświeżenia 30.08

- Zakres closeoutów: **14.07–29.08** (n=47). PNG + ten plik wygenerowane **30.08**.
- **25.08** (actual **4,5** kWh, cloud~100%): |APE| raw 5:00 **~150%** — typowy skok MAPE % przy małym mianowniku; RF mocno zawyżył dzień mokry.
- **26.08** clearing: raw za niski (classic undershoot) — też podnosi erę dual vs stan na 24.08.
- **29.08** daily 5:00 w CSV = **peak D-1 (20,72 kWh)** — brak launchd 05:00 (burza/sen); midday 12:00 = prawdziwy run (14,87). CS4 pick EOD **21,5** vs actual **21,1**.
- Era dual **27.07–29.08** (n=34): MAPE raw **15,7% / 15,9%** (wcześniej do 24.08: 11,0% / 10,0%, n=29).
