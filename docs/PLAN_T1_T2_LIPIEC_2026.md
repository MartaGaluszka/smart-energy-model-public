# Plan T1–T2 (lipiec 2026) — raw RF, closeouty, potem korekta

**Stan na 2026-08-02:** GPS + ICON + target PVE · **dual: 16 + CS4 + XGB+TS shadow** · korekta **OFF** · ocena na **raw** · UKMO = obserwacja ręczna · geometria **park** · **EA:** skala chmur + FI (backlog).

Powiązane: [NOTATKA_RETRENINGI_LIPIEC_2026.md](NOTATKA_RETRENINGI_LIPIEC_2026.md) · [UPDATE_2026-07-26_cs4-dual.md](UPDATE_2026-07-26_cs4-dual.md) · [UPDATE_2026-08-02_error-analysis-cloud-fi.md](UPDATE_2026-08-02_error-analysis-cloud-fi.md) · [CHANGELOG_ML.md](CHANGELOG_ML.md)

---

## Co zostało zrobione (do 26.07) — skrót

| Temat | Status |
|-------|--------|
| ICON + PVE + expanding window | ✅ |
| Closeouty ≥7 dni (raw) | ✅ / zbieranie dalej |
| **CS4** gate ACCEPT + **dual launchd** (16 primary + CS4) | ✅ 26.07 |
| `train_dual_weekly.sh` niedziela | ✅ (przeładuj: `./mlops/install_launchd.sh`) |
| UKMO oneshot (opad + RF) | ✅ — **nie** do prod; obserwacja ręczna |
| Geometria dachu | ❌ park (CS4+Geom nie bije CS4) |
| Adjust / cloudy tuning | OFF do decyzji D8 |
| `pvlib` / clearness | ✅ w CS4 (Haurwitz+astral; Ineichen padł) — bez dalszego eksperymentu |

---

## Najbliższe ~2 tygodnie (26.07 – ~09.08) — realistycznie

> **Jednym zdaniem:** zbierać dual closeouty (16 vs CS4) + notatki na złe dni (Accu/MB/**UKMO**) + ewentualnie **D8 adjust symulacja**; bez retrainu UKMO, bez geometrii, bez nowych bibliotek.

| Priorytet | Co | Gate / wynik | Czas |
|-----------|-----|--------------|------|
| **P0** | Closeouty 22:42: raw **16** + **CS4** (`daily_cs4` / `midday_cs4`) vs app | tabela 16 vs CS4 ≥7 dni po dualu | codziennie |
| **P0** | Prezentacja / ściąga — dual + CS4 tydzień 19–25 | slajd z REPORT | 1–2 h |
| **P1** | **D8:** raw vs (symulowany) adjust vs app na ≥7 closeoutach | włączyć adjust tylko warunkowo albo zostawić OFF | ½–1 dzień |
| **P1** | Notatki na **gorsze dni:** Accu + MB + **UKMO OM** (mm / first_wet) vs ICON — **ręcznie** | czy UKMO systematycznie bliżej obserwacji dachu | 5–10 min/dzień |
| **P1** | **Error Analysis (EA):** skala chmur 0–1 vs 0–100 + feature importance (chmury vs godzina/DOY) w MLflow | [UPDATE_2026-08-02_error-analysis-cloud-fi.md](UPDATE_2026-08-02_error-analysis-cloud-fi.md) · checklista EA.1–EA.7 | ½–1 dzień (po obronie lub gdy podejrzany bug skali) |
| **P2** | Gdy wyjdzie IMGW `2026_07_s.zip`: `compare_cloud_sources` | audyt ICON vs Balice | gdy ZIP |
| **Park** | Retrain UKMO · geometria · `pvlib` Ineichen · nowe cechy | — | po obronie / gdy P0–P1 OK |

### Biblioteka pogodowa Python (`pvlib`)

W notatkach / SCIĄG: **`pvlib`** = clear-sky / clearness (nie osobne API pogody — pogodę nadal bierze **Open-Meteo**).

| | |
|--|--|
| **Czy brać na testy teraz?** | **Nie trzeba** — clearness jest już w **CS4** (Haurwitz + `astral`; Ineichen z `pvlib` padł na pandas). |
| **Kiedy wrócić?** | Tylko jeśli chcecie porównać Haurwitz vs Ineichen oneshot — **nie** blokuje 2 tygodni. |
| **Nie mylić z:** UKMO / ICON (to modele NWP w Open-Meteo), Accu/MB (UI / `weather_notes`). |

### UKMO — kandydat do **obserwacji ręcznej** (gorsza pogoda)

**Nie produkcja, nie retrain.** Oneshot 19–25.07: timing deszczu bywa lepszy (np. 24.07); RF bez retrainu **zawyża** PV (MAE 8 vs 4).

**Protokół na złe dni (5–10 min):**

1. Wieczór / po deszczu: wpis w `weather_notes` lub wiersz w tabeli PLAN.  
2. Kolumny: dzień · app kWh · ICON Σmm / cloud · **UKMO Σmm / first_wet** (oneshot lub meteogram MB) · Accu mm · raw 16 · raw CS4.  
3. Pytanie: czy UKMO **pierwszy deszcz / mm** bliżej dachu niż ICON?  
4. Po ≥5–7 **złych** dniach: werdykt — zostawić jako notatki / kiedyś retrain / porzucić.

```bash
# szybki oneshot (bez zmiany .env)
./scripts/analysis/run_ukmo_tests.sh --start YYYY-MM-DD --end YYYY-MM-DD
```

CSV: `oneshot_icon_vs_ukmo_precip.csv` · `oneshot_rf_icon_vs_ukmo_daily.csv`.

---

## Zasady (ustalone 19.07)

| Zasada | Status |
|--------|--------|
| W ocenie i na obronie trzymać się **raw** (`predicted_kwh_raw`) | ✅ |
| Korekta operacyjna **wyłączona** w `.env` / domyślnie w kodzie | ✅ `FORECAST_OPERATIONAL_ADJUST=0` |
| Cloudy **nie** skaluje D+1/D+2 (nawet gdy adjust kiedyś włączymy) | ✅ poprawka w `intraday_forecast_adjust.py` |
| Po **≥7 closeoutach** (T1): raw vs adj vs app → decyzja o korektcie | ⏳ zbieranie |
| **Nie w T1:** agresywne kręcenie `FORECAST_CLOUDY_*` / `INTRADAY_BLEND` | ✅ |

Historia 19.07 (5:00 / 12:00) przepisana: w tabeli `predicted_kwh` = raw.

---

## Tydzień 1 (~17–23.07) — wdrożenie + zbieranie

| Dzień | Co | Po co | Gate | Status |
|-------|----|-------|------|--------|
| **D1** | `OPENMETEO_MODEL=icon_seamless` w `.env` + podpięcie w `fetch_weather` / kliencie OM | Naprawa „gładkich” chmur | diff chmur vs `best_match` na 09/12.07 (ICON lepszy) | ✅ 17.07 |
| **D1–D2** | Refetch archiwum ICON (+ GPS wcześniej) + **retrening** RF | Model uczy się na tej samej pogodzie co produkcja | `compare_model_change`: Test MAE ≤ +0.02 → ACCEPT | ✅ ICON 17.07; **PVE** 18.07 (ACCEPT operacyjny) |
| **D2–D7** | Zbieranie closeoutów 22:42 (cel: **≥7 dni**) na GPS+ICON+**PVE** | Paliwo pod decyzję o intraday / cloudy | **nie** kręcić blendu; ocena na **raw** | 🔄 od ~18–19.07 |
| **D3–D7** | Obserwacja poranek vs prognoza (bez włączania geometrii) | Decyzja o `PANEL_GEOMETRY` | notatki 2–3 dni pochmurne + 2–3 słoneczne | 🔄 |
| — | Korekta OFF + tabela = raw; cloudy nie na D+1/D+2 | Stabilny baseline T1 | — | ✅ 19.07 |

**Nie w T1:** agresywne kręcenie `FORECAST_CLOUDY_*` / `INTRADAY_BLEND` (za mało dni).

### Closeouty do zebrania (checklist T1)

Cel: ≥7 dni z wieczornym closeoutem 22:42 na modelu PVE+ICON (od **18.07** / pierwszej pełnej doby).

| Data | Closeout | Raw 5:00 vs app | Notatki |
|------|----------|-----------------|---------|
| 18.07 | ✅ | raw 5:00 ~29,1 vs app 26,6 | burza / krótkie przerwy |
| 19.07 | ✅ (dogoniony 21.07; evening padł na run_at) | raw 5:00 26,89 vs 27,3 (APE 1,5%); MAPE dziś ~1,3%; D+1 18.07 12:00 APE 1,6% | burza; raw trafiony |
| 20.07 | ✅ (re-run 21.07 rano; evening 20.07 padł na run_at) | raw 5:00 33,76 vs 37,4 (APE 9,7%); MAPE dziś 8,8%; D+2 18.07 5:00 APE 1,7%; szczyt 13:00 vs prog 12:00 | słonecznie, model niedoszacował |
| 21.07 | ⏳ closeout 22:42 / dogoń | raw 5:00 **27,55** vs app **18,8** (APE ~−32%); raw model wieczór ~25,1 | **pochmurny**; **AccuWeather dziś-na-dziś:** RealFeel 20° / shade 18°, krótkotrwały przelotny opad, UV 6, Brightness **5**, wiatr W 20 / porywy 46, opady **70%** (burza 14%), deszcz **2,8 mm** (~1,5 h), cloud **71%**; ICON śr. cloud ~85% (best_match ~48%); próby → „Jednorazowe próby 21.07” |
| 22.07 | | (oczekiwane) | **AccuWeather dziś-na-dziś (22.07 wieczór):** Max 22° / RF 24° / shade 21°, częściowo słonecznie, UV **8**, Brightness **9**, wiatr W 13 / 30, opady **0 mm** (P=25%), cloud **27%**, ostrzeżenie susza — **jasny dzień**; ICON forecast cloud ~79% / precip 0 (AW mniej chmur). Wcześniejsza AW z 21.07 na 22.07: cloud 46%, Brightness 7 |
| 23.07 | ⏳ closeout 22:42 | raw 5:00 **25,8** → 16:51 **25,2**; hybryda 16:00 **21,0** (FoxESS do 16:00 = **18,8**); app ~17:37 **19,8** (+ deszcz, PV~245 W) | **pochmurny/deszcz**; AW dziś-na-dziś: cloud **65%**, deszcz **7 mm** P=100%; AW na 24.07: cloud 72%, 2,6 mm; oneshot chmur → sekcja **Notatki wdrożeniowe — 23.07** |
| 24.07 | ⏳ closeout 22:42 | raw 5:00 **21,5** · midday raw **19,2** / hybryda **13,3** (FoxESS ~4,5) | **AW dziś-na-dziś:** Max 20° / RF 20° / shade 19°, przelotny opad, UV **4**, Brightness **4**, WNW 17/41, opady **3,4 mm** (P=87%), cloud **67%**, ostrzeżenie susza · obserwacje: 9–10 prześwity; ~12:30 deszcz; ~13:56 deszcz+słońce; **~14:20** zanik słońca, intensywny deszcz · AW z 23.07 na dziś: 72%/2,6 mm · MB/UKMO notes w `weather_notes` |
| 25.07 | | | **AW z 24.07 na jutro:** Max 24° / RF **27°** / shade 23°, cieplej, UV **7**, Brightness **5**, SW 9/24, opady **0 mm** (P=2%), cloud **71%** (korekta: wcześniej błędnie 7%) — suchy, pochmurny · `weather_notes` id 54 |
| 27.07 | ✅ closeout 22:44 (`--skip-sync` + plant CSV do 22:42) | **app/CSV ≈19.14** · daily raw **19.10** (błąd **+0.04**) · midday **17.97** (+1.17) · CS4 daily 17.99 / midday 16.05 | **zły dzień / burza:** dach ciemny → deszcz ~15:55 → burza+ulewa ~16:06 · AW 6 mm / MB ~3–7.5 · oneshot ICON 3.4 mm RF 18.1 vs UKMO 7.0 mm RF 23.1 · szczyt rzeczywisty **14:00 (3.83)** vs prog daily 07:00 · `weather_notes` 65–69 · [UPDATE_2026-07-27_icon-ukmo-mb.md](UPDATE_2026-07-27_icon-ukmo-mb.md) |

---

## Tydzień 2 (24–31.07) — operacja + eksperymenty

### Realistyczny skrót (24.07) — mało czasu

Jeśli nie zdążymy całego T2: **jedna rzecz do wspólnego testu = CS4** (low+mid + clearness) + `compare_model_change` (±0.02).  
Reszta (geometria, IMGW ZIP, tuning `.env` cloudy, osobno B vs CS1) → **park**: oneshoty już są w CSV / PLAN, na salę wystarczy „kandydat CS4, nie wdrożony”.  
D8 (raw vs adjust) zostaje **tylko jeśli** macie ≥7 closeoutów — nie blokuje testu CS4.

### Kolejność priorytetów T2 (ustalone 21.07; skrócone 24.07)

> **Jednym zdaniem:** przy braku czasu → **CS4 + gate**; pełna ścieżka poniżej tylko gdy zostanie slack.

1. **CS4** (low+mid + clearness) → `compare_model_change` — **priorytet #1 przy małym czasie**.
2. (Opcja) sam low+mid (B) albo sam clearness — tylko jeśli CS4 REJECT / ciekawość leave-one-out.
3. Potem geometria paneli (D10–D12), gate ±0.02 MAE — **park jeśli brak czasu**.
4. Równolegle: cloudy/intraday adjust (symulacja) — decyzja D8; nie mieszać z CS4 w jednym dniu.

| Dzień | Co | Po co | Gate |
|-------|----|-------|------|
| **D8** | Analiza 7+ closeoutów: **raw vs (symulowany) adj vs app** — kiedy intraday / cloudy pomaga / szkodzi | Decyzja: zostawić OFF · blend 0.65→np. 0.5 · albo „nie skaluj, gdy \|błąd rano\| &lt; X%” · złagodzić cloudy | APE midday ≤ APE daily na ≥70% dni **albo** jasny werdykt „raw wystarczy na T2” |
| **D9** | Lekki tuning chmur w `.env` (`THRESHOLD` 60–70, `EXTRA_SCALE` 0.5–0.6) — **tylko jeśli D8 każe włączyć adjust** | Pochmurne poranki bez wait na ML | 2–3 case study pochmurne (w tym **21.07**) |
| **D9–D11** | **Priorytet cech:** `cloud_cover_low` / `cloud_cover_mid` + `compare_model_change` | Ciężkie chmury (jak 21.07) | ACCEPT jeśli MAE↓ na pochmurnych **i** Test MAE ≤ +0.02 |
| **D10–D12** | Opcja A: `PANEL_GEOMETRY_FEATURES=1` + `compare_model_change` — **po** warstwach chmur | Kąt padania / kształt dnia | ACCEPT / REJECT (±0.02 MAE) |
| **D10–D12** | Opcja B (jeśli geometria REJECT): odświeżyć profil błędu (`build_error_profile`) | Tania poprawa operacyjna | — |
| **D13–D14** | Gdy wyjdzie `2026_07_s.zip`: `compare_cloud_sources` na 09/12.07 + inne złe dni vs Balice USL | Audyt ICON vs IMGW | jeśli IMGW ≈ ICON → zostaw; jeśli nie → REVIEW modelu OM |
| **D14** | Krótki wpis w `CHANGELOG_ML` + ewentualnie 1 akapit w `02_ML` | Domknięcie sprintu | — |

### Kolejny etap (po T2 / po prezentacji) — backlog

**Nie w tym tygodniu:** pełne coverage, dual pipeline live, retrain 19 cech, retrain UKMO, JUnit (to Python → **pytest**).

**Małe testy (opcjonalnie, 30–60 min) — invarianty:**
1. Σ dodatnich Δ`PVEnergyTotal` godzin = dzienny app (fixture 1 dnia).
2. `predicted_kwh_raw` == ścieżka bez korekty gdy `FORECAST_OPERATIONAL_ADJUST=0` (raw ≠ mylone z adjust).
3. `feature_columns` w `pv_hourly_model.joblib` = **16** (CS4 = osobny `*_cs4.joblib`, nie produkcja).

Punkt startu: `tests/test_pv_pipeline_smoke.py` (już jest smoke).

**Pomysły ML (park):**
- Retrain **UKMO** (osobny eksperyment) — na razie tylko **obserwacja ręczna** na złe dni (PLAN § 2 tygodnie).
- Geometria paneli — park (CS4+Geom nie bije CS4).
- `pvlib` Ineichen vs Haurwitz — opcjonalny oneshot, nie priorytet.
- IMGW `2026_07_s.zip` + audyt Balice.
- Conditional adjust po D8.

**Error Analysis — TODO (MLflow / pipeline danych)** — szczegóły: [`UPDATE_2026-08-02_error-analysis-cloud-fi.md`](UPDATE_2026-08-02_error-analysis-cloud-fi.md)

| ID | Status | Co |
|----|--------|-----|
| **EA.1** | `[ ]` | Audyt skali `cloud_cover_*` w DB (0–1 vs 0–100, outliery) |
| **EA.2** | `[ ]` | Zgodność jednostki z Open-Meteo + brak podwójnego skalowania w feature pipeline |
| **EA.3** | `[ ]` | ICON vs Accu/MB vs PV na złych dniach (24.07, 27.07, 01–02.08) |
| **EA.4** | `[ ]` | Feature importance MLflow / joblib: chmury vs `hour` / day-of-year (16, CS4, XGB+TS) |
| **EA.5** | `[ ]` | Jeśli czas ≫ chmury → oneshot (interakcje / bez DOY) + `compare_model_change` |
| **EA.6** | `[ ]` | Przy bug skali → naprawa + retrain + `CHANGELOG_ML` |
| **EA.7** | `[ ]` | Akapit Error Analysis w docs / obrona (po faktach z EA.1–4) |

**Werdykt etapu:** prezentacja > testy; duże dziury targetu (GPS / ICON / PVE) domknięte; kolejne „poprawki wyniku” = **CS4 / pogoda / EA skali+FI**, nie suite testów.

---

## Komendy szybkie

```bash
# Prognoza bez korekty (stan domyślny T1)
python scripts/forecast_pv.py

# Symulacja adjust — TYLKO RĘCZNIE (nie CRON / nie midday produkcyjny)
FORECAST_OPERATIONAL_ADJUST=1 python scripts/forecast_pv.py --run-label manual_adjust_sim
```

```bash
# Włączenie korekty dopiero po D8 (jeśli gate OK)
# w .env: FORECAST_OPERATIONAL_ADJUST=1
```

### Symulacje adjust (ręczne, nie produkcja)

| Kiedy | Run | Dziś raw → adj | App final | D+1 / D+2 (adj vs raw) | Werdykt |
|-------|-----|----------------|-----------|-------------------------|---------|
| 21.07 ~19:38 | `manual_adjust_sim` | ~25,1 → **~18,7** (skala 0,82: intraday 16,7/22,9 + chmury×0,60) | **18,8** | 22.07 ~35,2 vs ~31,6; 23.07 ~25,5 vs ~21,7 | **Dziś trafił**; D+1/D+2 podbił vs raw → nie włączać przed D8 |

### Jednorazowe próby 21.07 (notatka — co znaczy „test” vs „na stałe”)

**Po ludzku:**

| | Co to znaczy | Co robimy |
|--|--------------|-----------|
| **Jednorazowo / test** | Odpalamy skrypt **raz**, patrzmy liczby. Model w CRON / `.joblib` / `.env` **się nie zmienia**. | Wolno robić od razu (zrobione 21.07 wieczór). |
| **Na stałe** | Włączamy w produkcję: nowy trening, albo `FORECAST_OPERATIONAL_ADJUST=1` w `.env`, CRON używa korekty codziennie. | Dopiero gdy mamy **≥7 closeoutów** i świadomą decyzję (**D8**), żeby nie zepsuć jutra jak 20.07 midday. |

**Wyniki prób vs app 18,8 kWh (ICON, ten sam styl RF):**

| Próba | Pred | Dokładność dziś | Werdykt na dziś |
|-------|------|-----------------|-----------------|
| baseline 16 cech | ~25,6 | ~64% | za wysoko |
| + `cloud_low`/`cloud_mid` | ~24,2 | ~71% | **trochę lepiej**, nadal za wysoko |
| geometria dachu | ~25,5 | ~65% | prawie bez zmian (−0,1 kWh) |
| **adjust** (`ADJUST=1` ręcznie) | ~18,7 | **~99%** | **trafia dziś**; na D+1/D+2 w tej samej symulacji **zawyżał** |

### Pakiet prób cech 21.07 (wszystkie po kolei)

CSV: `data/processed/oneshot_feature_trials_20260721.csv`  
Actual app **18,8**. MAE = Test 80/20 na roku treningowym.

| # | Wariant | Test MAE | Pred 21.07 | Dokł. 21.07 |
|---|---------|----------|------------|-------------|
| A | baseline 16 | 0.650 | 25.58 | 63.9% |
| B | + cloud_low+mid | 0.630 | 24.20 | 71.3% |
| C | low+mid zamiast total | 0.656 | 24.44 | 70.0% |
| D | + rad_effective | 0.637 | 25.41 | 64.8% |
| E | + precip_flag+precip_3h | 0.647 | 26.33 | 59.9% |
| F | + visibility / low_vis | 0.654 | 25.90 | 62.2% |
| G | + geometria | 0.641 | 25.46 | 64.6% |
| H | + cloud_heavy (średnia low+mid) | **0.620** | 24.15 | 71.6% |
| I | low+mid + rad_effective | 0.626 | **23.94** | **72.7%** |
| J | low+mid + precip | 0.630 | 24.70 | 68.6% |
| K | full kandydaci (27 cech) | **0.610** | 24.51 | 69.6% |
| L | adjust sim (bez retrenu) | — | **18.7** | **~99%** |

**Werdykt pakietu (tylko próby, nie wdrożenie):**

1. Najlepsze **cechy ML** na dziś: **I** (low+mid + rad_eff) i **H** (cloud_heavy) — ~24 kWh, ~72% dokładności; wciąż ~5 kWh za wysoko.
2. **Precip / visibility / sama geometria** — słabe lub gorsze na 21.07.
3. **K full** ma najlepszy Test MAE (0.610), ale na dziś nie bije prostego I — ryzyko przeuczenia / zbędnych cech.
4. **Adjust** nadal jedyny wariant blisko 18,8 — decyzja na stałe dopiero D8.
5. Kandydat T2 do `compare_model_change`: najpierw **B/H/I** (warstwy chmur ± rad_effective), nie full dump.

### Runda 2 — nowe cechy (21.07, wcześniej nie testowane)

CSV: `data/processed/oneshot_feature_trials_20260721_runda2.csv`

| # | Wariant | Test MAE | Pred 21.07 | Dokł. |
|---|---------|----------|------------|-------|
| A0 | baseline (ref) | 0.650 | 25.58 | 63.9% |
| **Q** | **+ cloud_frac_low** (low/total) | 0.631 | **23.77** | **73.6%** |
| **AD** | **deltas 1h + low+mid** | **0.627** | 23.85 | **73.1%** |
| P | + cloud_low × rad | 0.632 | 24.12 | 71.7% |
| AB | low+mid + clearness | 0.630 | 24.40 | 70.2% |
| O | + rad × incidence | 0.645 | 24.96 | 67.3% |
| M | + clearness | 0.640 | 25.47 | 64.5% |
| S/T/U/V/Y/Z/AA | hour/doy/wind/humid×cloud/flags/high/snow | ≥0.635 | często gorsze | ≤64% |

**Werdykt rundy 2:** nowe „wygrywające” to znowu **rodzina chmur** (`cloud_frac_low`, delty cloud/rad + low/mid) — ~23.8 kWh / ~73%, nadal ~5 kWh za wysoko. Kalendarz (doy), wiatr kierunek, humid×cloud, cloud_high, śnieg — **nie pomagają** na dziś. Nadal żaden wariant ML nie bije **adjust ~18.7**.

### Runda deszcz (21.07)

CSV: `data/processed/oneshot_feature_trials_20260721_deszcz.csv`

**Ważne:** ICON archive na 21.07 daylight ma **0.0 mm** precip we wszystkich godzinach — Accu mówiło **2,8 mm**. Cechy deszczu z OM **nie widzą** deszczu Accu na ten dzień.

| Wariant | Test MAE | Pred | Dokł. |
|---------|----------|------|-------|
| baseline | 0.650 | 25.58 | 63.9% |
| + precip / flag / 3h / cum / kit | 0.642–0.665 | 25.6–26.7 | **58–64%** (często gorzej) |
| R14 rain + low+mid | 0.635 | 25.19 | 66% (zysk od **chmur**, nie deszczu) |

**Werdykt deszcz:** same cechy deszczu **nie pomagają** na 21.07 (i pogarszają pełny kit). Sens mają dopiero gdy źródło pogody raportuje opad zgodnie z rzeczywistością; dziś problem to **chmury/radiacja ICON**, nie brak kolumny deszczu w modelu.

### Miks chmur + proxy „mokrego dnia” (gdy API ma 0 mm)

CSV: `data/processed/oneshot_feature_trials_20260721_mix_proxy.csv`

**Proxy najlepiej skorelowane z prawdziwym deszczem (OM), gdy precip bywa >0:**  
`cloud_heavy` 0.31 · `cloud_mid` 0.29 · `proxy_overcast` 0.28 · `proxy_wet_score` 0.25 · niska `visibility` −0.23 · wilgotność 0.20.

Na godzinach mokrych vs PV: najsilniej **`proxy_overcast` (−0.42)**, potem rad / cloud / `wet_score`.

| Wariant | MAE | MAE dni mokre | Pred 21.07 | Dokł. |
|---------|-----|---------------|------------|-------|
| baseline | 0.650 | 0.648 | 25.58 | 63.9% |
| MIX4 compact (low/mid/frac/heavy/rad_eff/delta) | 0.625 | 0.570 | 23.50 | 75.0% |
| **MIX+PROXY full** | **0.614** | **0.561** | **23.27** | **76.2%** |
| PROXY1 sam wet_score | 0.621 | 0.619 | 23.68 | 74.1% |

Na 21.07 ICON: precip=0, ale `wet_score`≈0.58 i 6/16 h `overcast` — proxy **włącza się mimo braku mm w API**.

**Rekomendacja T2 (przygotowanie na deszcz + chmury):**  
1) zestaw chmur **MIX4** lub **MIX+PROXY** (`wet_score` / overcast zamiast surowego `precip_mm`),  
2) nie polegać na samym `precipitation_mm` z OM,  
3) nadal gate `compare_model_change`; adjust osobno na D8.

### Notatki wdrożeniowe — miks chmur (próby 20–21.07)

**Kontekst liczb:**

| Metryka | Wartość | Źródło |
|---------|---------|--------|
| Typowy **Daily MAE** modelu produkcyjnego (test 80/20) | **~3,7 kWh/d** | `hourly_model_tuning_summary_production.csv` |
| Closeouty live 14–20.07 (actual app) | śr. **~28 kWh**, zakres **10,9–37,4** | `forecast_validation.csv` |

**Dwa dni — ten sam miks (jednorazowo, bez wdrożenia):**

| Dzień | Typ | App | Baseline pred / błąd | MIX+PROXY (lub MIX2) | vs Daily MAE ~3,7 |
|-------|-----|-----|----------------------|----------------------|-------------------|
| **21.07** | pochmurny | **18,8** | 25,6 / **+6,8** (~36%) | **23,3 / +4,5** (~24%) | +4,5 **lekko powyżej** normy |
| **20.07** | słoneczny | **37,4** | 32,7 / **−4,8** (~13%) | **33,6 / −3,8** (~10%) | −3,8 **w okolicy** normy |
| 21.07 raw 5:00 live | — | 18,8 | — | 27,6 / **+8,8** | **poza normą** |
| 20.07 raw 5:00 live | — | 37,4 | — | 33,8 / **−3,6** | w normie |

Szczegóły 20.07: ICON cloud ~38%, wet_score ~0.31, 0 h overcast; MIX2 **33,64** (−3,76, dokł. 89,9%); MIX+PROXY **33,54** (−3,86, 89,7%).

**Werdykt wdrożeniowy:**

1. **18,8 kWh** — niski lipiec, ale **nie ekstremum** (np. 15.07 = 10,9). Słaby / pochmurny dzień, nie awaria.
2. Na **21.07** miks ściąga błąd z +6,8 → **+4,5** — nadal **lekko powyżej** Daily MAE (~3,7), ale dużo lepiej niż raw rano (+8,8). Na niskim dniu te 4,5 ≈ **24%**; przy ~30 kWh byłoby ~15%.
3. Na **20.07** miks **nie psuje** słonecznego dnia — lekko **podnosi** pred (32,7→33,6), błąd **−3,8 ≈ norma** Daily MAE; zbliżony do live raw 5:00 (−3,6).
4. **Razem:** miks działa w **obie strony** (pochmurny ↓ zawyżenia, słoneczny ↑ niedoszacowania) → **warty kandydat T2** (`compare_model_change`), **nie** włączać do produkcji po 1–2 dniach.
5. **Adjust** (~18,7 na 21.07) to osobna warstwa operacyjna — decyzja dopiero **D8**, nie zamiennik cech.

### Notatki wdrożeniowe — 23.07 (oneshot chmury + live)

**Kontekst dnia (live, ~17:30–17:40):**

| Metryka | Wartość | Źródło |
|---------|---------|--------|
| AccuWeather dziś-na-dziś | Max 18° / RF 21° / shade 17°, przelotne opady, UV 8, Brightness **5**, wiatr W 17 / porywy 54, opady **7,0 mm** (P=100%, burze 20%, ~4,5 h), cloud **65%**; alarmy burze+powódź+susza | `weather_notes` 23.07 16:56 |
| AccuWeather na jutro 24.07 | Max 20° / RF 20° / shade 18°, UV 6, Brightness 5, WNW 17/39, opady **2,6 mm** (P=88%), cloud **72%** | `weather_notes` 23.07 17:07 |
| Raw RF 5:00 → 16:00/16:51 | dziś **25,8 → 25,2**; jutro **15,2 → 18,5**; pojutrze **~34,2** | `pv_forecast_*` / `forecast_history` |
| Hybryda 16:00 / 16:51 | dziś **21,0** (FoxESS do 16:00 = **18,8** + RF reszta) | peak / daily |
| App ~17:37 | **19,8 kWh**; chwilowe PV ~**245 W**, zaczął padać deszcz | obserwacja użytkownika |
| Ostatni sensowny PVE w bazie | ~16:48 → **~19,3 kWh** dnia; potem śmieciowy odczyt `PVEnergyTotal=0` | `foxess_timeseries` |
| Szacunek EOD | **~20–20,5 kWh** (słaby ogon jak 21.07: 17:34→koniec było +0,9) | RF ≥17 ~0,6 + deszcz |

**Oneshot cech chmur (jednorazowo, bez zmiany `.joblib`):**  
Trening → 2026-07-22, RF jak produkcja (`max_depth=6`, …), split 80/20 `random_state=42`.  
CSV: `data/processed/oneshot_feature_trials_20260723_clouds.csv`

| Wariant | Test MAE | Pred. raw 23.07 | vs app ~19,8–20 |
|---------|----------|-----------------|-----------------|
| A baseline 16 (tylko `cloud_cover`) | **0.603** | 24,3 | +~4,5 |
| **B + `cloud_low` + `cloud_mid`** | 0.604 | **23,0** | +~3 |
| B2 + low+mid+high | 0.603 | 23,0 | +~3 |
| **H + `cloud_heavy`** (= średnia low+mid) | 0.609 | **25,1** | +~5 (najgorzej dziś) |
| Full low+mid+heavy | 0.605 | 23,5 | +~3,5 |
| C low+mid zamiast total | 0.654 | 22,5 | +~2,5 (gorszy Test MAE) |

ICON dziś (daylight w ramce): total ~**89%**, low ~**59%**, mid ~**54%**, high ~**48%**, heavy ~**56%** → **gap total−heavy ≈ +33** (total nasycony, warstwy nie „cięższe” niż total).

**Kiedy `cloud_heavy` pomaga (dni testowe 80/20):**

| Warunek | Heavy lepszy niż baseline | Δ daily MAE (H−A) |
|---------|---------------------------|-------------------|
| Jasne (cloud &lt; 50%) | ~**67%** dni | **−0,17** (pomaga) |
| Silna radiacja / total≈heavy | ~60–67% | lekko ujemny |
| Pochmurne (cloud ≥ 80%) | tylko ~**44%** | **+0,15** (szkodzi) |
| total ≫ heavy (Δ≥25) | ~**33%** | **+0,47** (mocno szkodzi) |

**Werdykt wdrożeniowy 23.07:**

1. Dzień **słaby / deszczowy** — podobny charakter do **21.07** (niski EOD, ogon &lt;1 kWh); do 16:00 już **18,8**, do 17:37 **19,8** (powyżej całego 21.07 = 18,8).
2. Oneshot jak 21.07: **B (low+mid osobno)** lekko ściąga zawyżenie (24,3→23,0), nadal **~3 kWh za wysoko** vs app — **nie** zamyka luki jak adjust.
3. **`cloud_heavy` dziś psuje** (25,1) i w CV wygrywa raczej na **jasnych** dniach, nie na ciężkim overcaście — **nie** brać jako „lek na pochmurne”.
4. Kandydat T2 bez zmiany: nadal **B / MIX warstw osobno** + `compare_model_change`; heavy tylko jako cecha pomocnicza albo wcale.
5. Produkcja / launchd / adjust: **bez zmian** (raw OFF adjust). Closeout 22:42 zbierze actual vs raw ~25.

### Notatki wdrożeniowe — oneshot clearness (24.07)

**Metoda (bez `.joblib`):** clear-sky GHI = **Haurwitz** + elevacja **astral** (GPS dach); cecha `clearness = radiation_wm2 / ghi_clear` (clip 0–1.5). Trening → 2026-07-22, RF jak produkcja.  
CSV: `data/processed/oneshot_feature_trials_20260723_clearness.csv` (+ `_cases.csv`).

| Wariant | Test MAE | Pred raw 23.07 | vs app 20,6 | Dokł.* |
|---------|----------|----------------|-------------|--------|
| A baseline 16 | **0.603** | 24,3 | +3,7 | 82% |
| CS1 + clearness | 0.605 | **23,0** | +2,4 | **88%** |
| CS2 clearness zamiast rad | 0.604 | 22,6 | +2,0 | **90%** |
| B + low+mid | 0.604 | 23,1 | +2,5 | 88% |
| **CS4 low+mid + clearness** | 0.605 | **22,3** | **+1,7** | **92%** |

\* \(100\times(1-|err|/20{,}6)\). Dziś clearness śr. ~**0,50** (słaby dzień).

**Werdykt:** clearness **lekko pomaga na 23.07** (jak low+mid), Test MAE ≈ remis z baseline (**nie** regresja duża). Najlepszy oneshot dnia: **CS4**. Na 21.07 sam clearness ≈ baseline; low+mid+clearness trochę lepiej. **Nie wdrażać** — kandydat T2 obok B, gate `compare_model_change`. (`pvlib` Ineichen padł na konflikcie pandas; Haurwitz wystarcza do oneshotu.)

**CS4 vs reszta (ten sam trening → 22.07):**

| Wariant | Test MAE | Pred 23.07 | vs app 20,6 | Dokł. |
|---------|----------|------------|-------------|--------|
| A baseline | 0.603 | 24,3 | +3,7 | 82% |
| B + low+mid | 0.604 | 23,1 | +2,5 | 88% |
| CS1 + clearness | 0.605 | 23,0 | +2,4 | 88% |
| **CS4 low+mid + clearness** | 0.605 | **22,3** | **+1,7** | **92%** |

**CS4 vs baseline — o ile lepiej (case study 20–23.07):**

| Dzień | App | Dokł. A → CS4 | Lepiej o | Błąd \|kWh\| ↓ o |
|-------|-----|---------------|----------|------------------|
| 20.07 | 37,4 | 89% → 91% | **+1,6 pp** | **−15%** (4,1→3,5) |
| 21.07 | 18,8 | 75% → 78% | **+3,2 pp** | **−13%** (4,7→4,1) |
| 22.07 | 33,5 | 87% → 87% | **+0,6 pp** | **−4%** (4,5→4,3) |
| **23.07** | **20,6** | 82% → **92%** | **+9,7 pp** | **−54%** (3,7→1,7) |

APE na 23.07: **18% → 8%**. Największy skok na słabym 23.07; na jasnym 20.07 / 22.07 poprawa mała.

**Wspólny test (gdy mało czasu):** trening z cechami CS4 → `compare_model_change` vs produkcja → ACCEPT/REJECT. Bez zmiany launchd / `.env` przed ACCEPT. Notatki Accu/MB i pełne D8 — tylko tło, nie warunek startu.

### Oneshot — UKMO vs ICON (opad, 21–24.07) — bez produkcji

**Kontekst:** na MB MultiModel timing deszczu 24.07 bliższy obserwacji dachu u **UKMO** niż ICON; NEMS nie jest darmowy API → kandydat darmowy = **`ukmo_seamless`** (Open-Meteo).

Skrypt: `scripts/analysis/oneshot_icon_vs_ukmo_precip.py`  
CSV: `data/processed/oneshot_icon_vs_ukmo_precip.csv` (+ hourly 24.07).

| Dzień | ICON Σmm (5–20) | UKMO Σmm | 6–11 / 12–15 ICON | 6–11 / 12–15 UKMO | Uwaga |
|-------|-----------------|----------|-------------------|-------------------|--------|
| 21.07 | 0,0 | 0,2 | 0/0 | 0,1/0,1 | oba „suche” vs Accu deszcz |
| 22.07 | 0,0 | 0,0 | — | — | jasny — OK |
| 23.07 | **10,3** | **11,9** | 1,3 / 2,8 | 3,4 / 3,3 | oba mokre (Accu ~7) |
| **24.07** | **0,0** | **3,8** | 0 / 0 | **0,4 / 2,7** | UKMO bliżej obserwacji (~deszcz od południa); ICON **ślepy na mm** |

**Werdykt:** oneshot pogodowy **TAK, zrobiony** — UKMO lepiej na **24.07**. **Nie** przełączać `OPENMETEO_MODEL` na stałe. Ewentualny test RF na pogodzie UKMO = osobny T2 (jak CS4), nie dziś do launchd.

### Oneshot RF — ten sam `.joblib`, pogoda ICON vs UKMO (21–24.07)

Skrypt: `scripts/analysis/oneshot_rf_icon_vs_ukmo.py` · CSV: `oneshot_rf_icon_vs_ukmo_daily.csv`.

| Dzień | Pred ICON | Pred UKMO | Δ | App | Dokł. ICON | Dokł. UKMO |
|-------|-----------|-----------|---|-----|------------|------------|
| 21.07 | 25,0 | **32,4** | +7,4 | 18,8 | **67%** | 28% |
| 22.07 | 30,6 | 35,4 | +4,8 | 33,5 | 91% | **94%** |
| 23.07 | 25,3 | 28,6 | +3,3 | ~19–20,6 | **~69%** | ~52% |
| 24.07 | 19,2 | 22,2 | +2,9 | (dzień w toku) | — | — |

**Werdykt:** UKMO w tym samym RF (uczonym na ICON) **podnosi** pred (+3…+7 kWh). Na słabych dniach **pogarsza** vs app; na jasnym 22.07 lekko pomaga. Lepszy timing opadu ≠ lepsza produkcja bez **retrainu** na UKMO. Produkcja zostaje na ICON.

### Oneshot — ICON vs IMGW Balice (czerwiec 2026) — bez produkcji

**Cel:** audyt wejść chmur (nie cecha RF). Skrypt: `scripts/analysis/oneshot_icon_imgw_clouds_june2026.py`.  
CSV: `data/processed/oneshot_icon_vs_imgw_balice_202606_{hourly,daily}.csv`.

| Metryka (720 h) | Wartość |
|-----------------|---------|
| ICON śr. cloud (baza, home/archive) | **70,8%** |
| IMGW Balice NOG → % | **58,0%** (~4,64/8) |
| Bias ICON−IMGW | **+12,8 pp** (ICON bardziej pochmurny) |
| MAE \|Δ\| | **21,3 pp** (dzień 5–20h: **19,7**) |
| Korelacja | **0,67** (5–20h: **0,71**) |

**Werdykt:** korelacja OK → ICON i stacja idą w tę samą stronę; ICON **lekko zawyża** chmury vs Balice (~+13 pp). Balice ≠ dach. **Nic nie wdrażamy.** Lipiec IMGW (`2026_07_s.zip`) → ten sam skrypt / `compare_cloud_sources` gdy wyjdzie (~pocz. VIII), pod case’y 21/23.07.

### Niedziela — CS4 (kandydat, równolegle do retrainu produkcji)

Launchd **5:00** i tak robi retrain **16 cech** → `pv_hourly_model.joblib`.

**CS4 nie podmienia produkcji automatycznie.** Po retrainie / ręcznie:

```bash
./scripts/analysis/run_cs4_sunday.sh
# → models/pv_hourly_model_cs4.joblib + gate + shadow forecast (run-label cs4_shadow)
```

Obserwacja kilka dni (dashboard + Accu/MB). **ACCEPT** z `compare_model_change` → dopiero wtedy ewentualna podmiana `.joblib` w launchd.

Cechy CS4: production + `cloud_cover_low_pct` + `cloud_cover_mid_pct` + `clearness` (Haurwitz).

---

### Co dalej z notatkami ręcznymi (Accu / MB → `weather_notes`)?

**To paliwo pod decyzje, nie cechy modelu.**

| Po zebraniu ≥7–14 dni | Co robisz |
|-----------------------|-----------|
| **Tabela w PLAN** | dzień · Accu mm/cloud · MB (meteogram) · ICON OM · app kWh · raw 5:00 |
| **Werdykt** | czy ICON **systematycznie** gubi deszcz / zawyża PV |
| **D8** | raw vs adjust vs app — notatki tłumaczą *dlaczego* dzień był zły |
| **T2** | czy warto low+mid / nic nie zmieniać |
| **Prezentacja** | „audyt jakości wejść bez płatnego API” |

**Nie:** nie wrzucasz notatek do RF, nie zmieniasz `.env` po 1 dniu.

### Mapowanie „inni → my → następny krok”

| Inni | Wy teraz | Sensowny następny krok |
|------|----------|------------------------|
| Warstwy chmur | oneshot low+mid | T2 + `compare_model_change` |
| Ensemble niepewności | MB UI | notatka w PLAN, bez API |
| Live rescale | adjust OFF | decyzja po ≥7 closeoutach (D8) |
| Satelita / kamera | brak | za ciężkie na T1 / dyplom |
| Clear-sky index | oneshot **CS4** (low+mid + clearness) | **wspólny test + gate** (±0.02) — realny priorytet przy małym czasie |

### Outlook Accu / aplika 14 dni (zrzut 21.07 wieczór)

| Dzień | Typ (ikona) | Tmax/Tmin | Uwaga pod closeout / próby |
|-------|-------------|-----------|----------------------------|
| 21 | części. słonecznie / chmury | 19/12 | **dziś** — app 18,8; case pochmurny ✅ |
| 22 | części. słonecznie | 22/12 | jaśniej (zgodnie z Accu 46%) |
| **23–24** | **przelotny deszcz** | 19/12 · 19/10 | dobre dni pod **proxy mokre** + raw vs app |
| **25** | **deszcz / zachmurzenie** | 24/11 | ciężki — idealny pod MIX+PROXY vs sam precip OM |
| 26 | prz. deszcz | 27/15 | |
| **27** | **deszcz** | 23/14 | |
| 28 | części. słonecznie | 24/13 | |
| **29–30 · 1.08** | **słońce** | 26–28 / 15 | kontrast — dni „łatwe” do porównania MAE |
| 31 | części. słonecznie | 26/14 | |

**Na T1:** closeouty **22–24.07** domykają ≥7 dni; **23–27** to naturalne paliwo pod notatki pochmurne/deszczowe (bez włączania cech).  
**Na T2:** po D8 warto wrócić do miksu na którymś z **25/27**, gdy OM znów pokaże 0 mm a rzeczywistość będzie mokra.

*(Szczegóły prób miksu 20.07 / 21.07 — w sekcji **Notatki wdrożeniowe — miks chmur** powyżej; oneshot 23.07 low/mid/heavy — **Notatki wdrożeniowe — 23.07**.)*

**Co z tego wynika (żeby nie gubić zapisków):**

1. **Możemy testować od razu** — nie czekamy z ciekawością / notatką.
2. **Nie włączamy niczego w produkcję po jednym dniu** — zwłaszcza adjust (20.07 pokazał, że midday potrafi pogorszyć).
3. Na D8 zestawiamy **wiele dni** raw vs adjust vs app → wtedy dopiero „włączyć / nie”.
4. `cloud_low`/`mid`: obiecujące w teście; **na stałe** = osobny trening + `compare_model_change` (T2), nie wieczorem po 1 dniu.
5. **`cloud_heavy`:** na 21.07 wyglądał OK, na **23.07 szkodzi**; w CV pomaga raczej na **jasnych** dniach — nie traktować jako fix na overcast.
