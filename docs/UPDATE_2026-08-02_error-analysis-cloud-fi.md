# Error Analysis — skala chmur + feature importance (MLflow / pipeline)

**Data:** 2026-08-02  
**Kontekst:** dni przejściowe / po froncie (m.in. 24.07 APE ~100%, 28–29.07 i 01–02.08 niedoszacowanie lub zawyżenie vs ICON) — materiał do dokumentacji technicznej i backlogu T2+.

Powiązane: [`PLAN_T1_T2_LIPIEC_2026.md`](PLAN_T1_T2_LIPIEC_2026.md) · [`CHANGELOG_ML.md`](CHANGELOG_ML.md) · [`UPDATE_2026-07-26_cs4-dual.md`](UPDATE_2026-07-26_cs4-dual.md) · live dual 26.07–01.08 (notebook slajd 9c)

---

## Hipotezy (do potwierdzenia / obalenia)

### H1 — mapowanie skali zachmurzenia w pipeline

Dostawcy API czasem podają zachmurzenie jako:

| Skala | Zakres | Ryzyko |
|-------|--------|--------|
| ułamek | 0.0–1.0 | jeśli model oczekuje 0–100 → drzewa uczą się „śmieci” |
| procent | 0–100 | jeśli ktoś ×100 drugi raz → saturation / złe progi |

**Hipoteza robocza u nas:** Open-Meteo ICON → kolumny `cloud_cover_percent` / `*_low/mid/high_percent` w `weather_data` (nazwy sugerują **0–100**), mapowanie w `src/data/weather_api.py` bez jawnego `×100`.  
**TODO:** twardy audyt min/max/kwantyle + porównanie z dokumentacją OM i z Accu/MB na tych samych godzinach (nie zakładać, że nazwa kolumny = prawda w każdym wierszu historycznym).

Jeśli skala kiedykolwiek była mieszana (stare `best_match` vs ICON, refetch) — RF/XGB mogą „wierzyć” w chmury za słabo albo w złym kierunku na dniach przejściowych.

### H2 — feature importance: chmury vs czas (godzina / day-of-year)

Jeśli w MLflow / `feature_importances_` model stawia **wyżej godzinę / dzień roku** niż `cloud_cover_*`, to na dniach przejściowych (front, burza nocna → szary ranek, prześwity) zawsze będzie popełniał błędy typu:

- **zawyżenie** przy realnie ciężkich chmurach (np. 24.07), albo  
- **niedoszacowanie** gdy ICON jest „za chmurny”, a dach ma prześwity (28–29.07, częściowo 01.08).

CS4 (low+mid+clearness) na tygodniu live 26.07–01.08 **nie** przebił primary 16 → problem może leżeć **głębiej w sygnale NWP / skali / wadze cech czasowych**, nie tylko w braku warstw chmur.

---

## Checklist TODO (MLflow / pipeline danych)

| # | Status | Zadanie | Jak / artefakt |
|---|--------|---------|----------------|
| EA.1 | `[ ]` | **Audyt skali chmur** w `weather_data` (ICON + ewentualnie archiwum) | `MIN/MAX/p50` dla `cloud_cover_percent`, low/mid/high; czy wartości ∈ [0,1] vs [0,100]; czy są outliery >100 |
| EA.2 | `[ ]` | Porównaj **jednostkę** z dokumentacją Open-Meteo (`cloud_cover` = %) i ze skryptem zapisu | `weather_api.py` · brak podwójnego skalowania przy feature engineering |
| EA.3 | `[ ]` | Sanity na złych dniach: ICON cloud vs Accu/MB vs produkcja | 24.07, 27.07, 01–02.08 · `weather_notes` |
| EA.4 | `[ ]` | **Feature importance** z ostatniego runu MLflow / `pv_hourly_model.joblib` | ranking: `cloud_cover_*` vs `hour` / `day_of_year` / radiacja; to samo dla CS4 i XGB+TS |
| EA.5 | `[ ]` | Jeśli FI: czas ≫ chmury → eksperyment | oneshot: mocniejsza waga chmur / interakcja cloud×hour / bez day_of_year → `compare_model_change` |
| EA.6 | `[ ]` | Jeśli skala zła w historii → naprawa pipeline + **retrain** (nie tylko dual shadow) | gate ACCEPT; wpis w `CHANGELOG_ML` |
| EA.7 | `[ ]` | Krótki akapit Error Analysis w `02_ML_predykcja_PV.md` / obrona | po EA.1–EA.4 (fakty, nie hipotezy) |

---

## Decyzja operacyjna (na teraz)

- **Nie** zmieniać primary 16 ani skali w prod przed EA.1–EA.4.  
- Zbieranie closeoutów + notatek pogodowych (Accu/MB/UKMO) zostaje.  
- EA.* = praca **po obronie / w T2+**, chyba że audyt skali wykaże oczywisty bug (wtedy hotfix P0).

---

*Dopisano 2026-08-02 — z dyskusji o Error Analysis (skala chmur + FI w MLflow).*
