# Dokumentacja projektowa — Smart Energy Mobile (Angular + Ionic)

**Wersja:** 0.3  
**Data:** 2026-07-25  
**Status:** draft do implementacji  
**Powiązane:** [ZADANIA_IMPLEMENTACJA_MOBILNA.md](ZADANIA_IMPLEMENTACJA_MOBILNA.md) (FastAPI **TA.***; advise/push MVP **T4.11+**)

**Cel:** Aplikacja mobilna Android (Ionic + Angular) korzystająca z istniejącego backendu danych, bazy i modelu ML PV z repozytorium `smart-energy-model`.

**Design:** motyw **Solar Graphite** (jasny, bursztyn + grafit; zieleń tylko jako akcent „oszczędność”).

---

## 1. Cel produktu

Aplikacja pomaga gospodarstwu z PV + magazynem (FoxESS) i rozliczeniem **net-billing / G12w (Tauron)**:

1. Symulować rachunek „tylko Tauron” vs rzeczywistość z autokonsumpcją.
2. Liczyć **ROI / czas zwrotu** na realnym profilu zużycia, nie na folderze sprzedawcy.
3. Optymalizować strategię baterii zimą (ładowanie w taniej strefie, rozładowanie w szczycie) z prognozą PV.
4. Dawać kontekst domowy (kalendarz, sezony, tryby behawioralne).

**Nie kopiujemy UI FoxESS** — własna marka, jasna paleta, inna nawigacja i typografia.

---

## 2. Gotowość względem obecnego projektu

| Warstwa | Stan w repo | Co trzeba dodać pod appkę |
|---------|-------------|---------------------------|
| Dane FoxESS | Sync API key → SQLite (`foxess_*`) | REST API + auth użytkownika; opcjonalnie OAuth (patrz §5) |
| Pogoda | Open-Meteo → `weather_data` | Endpointy prognozy pod optymalizator |
| ML PV | RF `models/pv_hourly_model.joblib` (16 cech, target PVE) | Serwis inference (FastAPI) + cache prognoz |
| Tauron | `tauron_bills`, `tauron_tariff`, skrypty importu | Formularz UI + API CRUD |
| G12w | `src/optimization/g12w_tariff.py` | API stref + okien ForceCharge |
| ROI | `src/financial/roi_calculator.py`, `prosumer_deposit.py`, RCEm | API symulacji + parametry CAPEX |
| Dashboard | Streamlit MVP (notatki / prognoza) | Osobna app Ionic — Streamlit zostaje ops |
| Docker | **brak** | `docker-compose` (DB + API) |
| OAuth Fox | Dziś: **API key** (`FOXESS_API_KEY`) | Spike: czy FoxESS Cloud daje OAuth2; fallback: powiązanie klucza w panelu |

**Werdykt:** dane i logika biznesowa są wystarczająco dojrzałe do projektu i MVP API. Brakuje warstwy mobilnej, Dockera i ujednoliconego backendu HTTP.

---

## 3. Design system — Solar Graphite

### 3.1 Tokeny kolorów

| Token | Hex | Użycie |
|-------|-----|--------|
| `--bg` | `#F2F0EB` | tło aplikacji |
| `--surface` | `#FAFAF8` | karty, bottom sheet |
| `--text` | `#1A1D21` | tytuły, wartości |
| `--text-muted` | `#5C636A` | podpisy |
| `--border` | `#E3DFD6` | ramki |
| `--solar` | `#E6A012` | CTA, PV, primary |
| `--solar-pressed` | `#C9860A` | hover/press |
| `--moss` | `#4F6F52` | **tylko** oszczędność / plus / ROI OK |
| `--grid` | `#3D4450` | pobór z sieci, serie „Tauron” |
| `--cost` | `#C45C26` | koszt / ostrzeżenie |

### 3.2 Typografia i UI

- Tytuły: serif z charakterem (np. Source Serif 4)
- UI: DM Sans / Satoshi
- Karty: cienka ramka, bez ciężkich cieni
- Wykresy: PV = `--solar`, sieć = `--grid`, oszczędność = `--moss`
- Unikać: granatu, cyanu FoxESS, fioletowych gradientów, „eco green” na całym ekranie

### 3.3 Branding vs FoxESS

- Własna nazwa (np. **Smart Energy** / **Dachowy Bilans**)
- Brak logo Fox, brak layoutu 1:1 aplikacji Cloud
- Dane Fox = źródło IoT; UI = produkt dyplomowy/domowy

---

## 4. Architektura docelowa

```mermaid
flowchart TB
  subgraph mobile [Ionic Angular Android]
    UI[Panele: Symulator ROI Bateria Kalendarz]
    Auth[Auth + Secure Storage]
  end

  subgraph docker [Docker Compose]
    API[FastAPI Backend]
    DB[(PostgreSQL lub SQLite volume)]
    ML[Model joblib + feature pipeline]
  end

  subgraph external [Zewnętrzne]
    Fox[FoxESS Cloud]
    OM[Open-Meteo]
    PSE[PSE RCE/RCEm]
  end

  UI --> API
  Auth --> Fox
  API --> DB
  API --> ML
  API --> Fox
  API --> OM
  API --> PSE
```

### 4.1 Stack

| Element | Wybór |
|---------|--------|
| Frontend | **Angular + Ionic** (Android first; Capacitor) |
| Backend | **FastAPI** (Python) — owija istniejące `src/*` |
| ML | ten sam `pv_hourly_model.joblib` + `src/features/*` |
| DB w Docker | **PostgreSQL 16** (produkcja app) *lub* SQLite na volume na MVP; migracja schematu z `config/database_schema.sql` |
| Sync Fox | joby w API / worker / cron w kontenerze (jak `mlops/`) |
| Wykresy | ApexCharts / Chart.js / ECharts w Ionic |

### 4.2 Kontenery (propozycja `docker-compose`)

- `db` — Postgres + volume
- `api` — FastAPI + mount `models/`
- `worker` (opcjonalnie) — sync FoxESS / Open-Meteo / RCE
- `admin` (opcjonalnie) — obecny Streamlit tylko lokalnie, nie w sklepie

---

## 5. Logowanie i FoxESS (OAuth 2.0)

**Wymaganie produktowe:** logowanie OAuth 2.0 do chmury Fox.

**Stan faktów w projekcie:** integracja oparta o **private API key** (API Management), nie o OAuth Authorization Code.

**Plan bezpieczeństwa:**

1. **Spike:** sprawdzenie dokumentacji FoxESS OpenAPI — czy jest OAuth2 / OIDC dla aplikacji trzecich.
2. Jeśli **tak:** Authorization Code + PKCE w Ionic → token w Secure Storage → backend wymienia / przechowuje refresh token w vault użytkownika.
3. Jeśli **nie / ograniczone:**
   - logowanie do **Waszej** aplikacji (OAuth2 własny IdP: Keycloak / Auth0 / Google),
   - w panelu użytkownika: **powiązanie konta Fox** przez wklejenie API key (szyfrowane at-rest) + opcjonalnie Device SN,
   - dokumentacja uczciwie opisuje ograniczenie API Fox.

**Zasada PII:** w DB nie trzymać nazwy stacji / SN w plaintext do prezentacji; SN tylko w vault API.

---

## 6. Panel użytkownika — procesy bazowe

### 6.0 Ekran startowy / sync

- Status ostatniego sync FoxESS (`foxess_device_meta.fetched_at`)
- Przycisk **Pobierz dane Fox** → `POST /api/v1/foxess/sync` (zakres dat)
- Status modelu ML + ostatnia prognoza dzienna
- KPI: produkcja dziś, SoC baterii, import/export dziś

---

## 7. Moduł 1 — Symulator Rachunków (Tauron vs Autokonsumpcja)

### 7.1 Zasada

Formularz stawek z faktury + historyczne logi falownika → porównanie kosztów.

### 7.2 Pola UI

- Opłata stała / abonament [zł/mies.]
- Energia strefa 1 / 2 [zł/kWh netto lub brutto — przełącznik]
- Dystrybucja strefa 1 / 2
- Moc umowna / opłata mocowa (opcjonalnie)
- Okres symulacji: miesiąc / rok / „ostatnie N miesięcy”

Zapis → `tauron_tariff` + wersjonowanie w `user_tariff_overrides`.

### 7.3 Logika (backend)

Źródła: `foxess_data` / `foxess_timeseries` (loads, feedin, gridConsumption, pvPower), opcjonalnie `meter_readings` / `tauron_bills`.

```
koszt_bez_PV ≈ sum(import_symulowany × stawki) + opłaty_stałe
  gdzie import_symulowany ≈ loads (zużycie domu) — gdyby 100% z sieci

koszt_z_PV ≈ sum(grid_import × stawki) + opłaty_stałe
  − wartość_depozytu(export × RCEm)   # net-billing

oszczędność = koszt_bez_PV − koszt_z_PV
```

### 7.4 Wizualizacja

- Wykres **słupkowy grupowany**: „Bez paneli” (`--grid`/`--cost`) vs „Z PV” (`--solar`) vs „Oszczędność” (`--moss`)
- Mini tabela: kWh z dachu / z sieci / oddane

### 7.5 Mapowanie kodu

- `FinancialAnalyzer` — `src/financial/roi_calculator.py`
- Depozyt — `src/financial/prosumer_deposit.py`
- Stawki — tabela `tauron_tariff`

---

## 8. Moduł 2 — Kalkulator ROI

### 8.1 Zasada

Roczne ROI i **lata do zwrotu** z realnych oszczędności (Moduł 1), nie z folderu sprzedawcy.

### 8.2 Wejścia użytkownika

- CAPEX instalacji [zł] (PV + falownik + opcjonalnie bateria osobno)
- OPEX roczny (serwis)
- Inflacja energii % (opcjonalnie)
- Tryb: „ostatnie 12 miesięcy z danych” **lub** „annualizacja z dostępnych miesięcy”

### 8.3 Wyjścia

- Oszczędność roczna [zł]
- ROI % = oszczędność_roczna / CAPEX
- Payback [lata]
- Porównanie z „założeniem sprzedawcy” (pole ręczne do kontrastu)

### 8.4 Wizualizacja

- Gauge / big number payback
- Wykres skumulowanych oszczędności vs CAPEX (linia przecięcia = zwrot)

---

## 9. Moduł 3 — Optymalizator Baterii (strategia zimowa)

### 9.1 Zasada

Suwaki G12w + plan ładowania nocą / rozładowania w szczycie; decyzja „czy ładować z sieci dziś w nocy” zależna od prognozy słońca (Open-Meteo + model RF).

### 9.2 UI

- Suwaki: cena strefa 1 / 2, sprawność baterii, min SoC rano, max DoD
- Toggle: zima / lato
- Timeline 24h: okna tanie (`g12w_tariff`) vs plan SoC

### 9.3 Algorytm (MVP → later) — tryb wyłącznie doradczy

**Zasada produktowa (MVP i okres walidacji ~1 rok):** system **tylko doradza**. Nie wysyła komend ForceCharge / WorkMode do falownika. Użytkownik widzi sugestie (dashboard + push) i **kontrfaktyczne oszczędności** („ile BYŚMY zaoszczędzili, gdyby automatyka była włączona”). Przycisk fizycznego sterowania jest **ukryty / zablokowany** do czasu potwierdzenia jakości algorytmu.

**MVP (reguły + powiadomienia):**

- Wylicz plan: force charge w oknach z `weekday_force_charge_windows()`, rozładuj w zone1, rezerwa SoC
- Wyświetl plan na dashboardzie + **push** z sugestią (np. „Dziś wieczorem warto naładować magazyn w taniej strefie 22:00–6:00”)
- Policz i pokaż `shadow_savings_pln` — oszczędność hipotetyczna vs faktyczne zachowanie instalacji
- Stały komunikat UI (banner): dlaczego pełna automatyka nie jest jeszcze dostępna (patrz §9.6)

**v2 (ML, nadal doradczo):**

- Prognoza PV jutro (`pv_hourly_model` + Open-Meteo)
- Jeśli jutro PV_forecast > próg → sugestia: **nie** ładuj nocą z sieci (lub mniej)
- Jeśli jutro słabo → sugestia: ładuj w taniej strefie do SoC_target

**v3 (po ~roku testów, osobna decyzja produktowa):**

- Odblokowanie przycisku sterowania falownikiem (opt-in + audit log) — poza zakresem MVP

### 9.4 Wizualizacja

- Wykres liniowy: SoC planowany, cena strefy (schodek), PV forecast
- Kolory: ładowanie `--solar`, rozładowanie `--moss`, sieć `--grid`

### 9.5 Mapowanie kodu

- `src/optimization/g12w_tariff.py`
- `mlops/foxess_control.py` — **nie wywoływać w MVP**; tylko dokumentacja przyszłego mostu
- Analizy: `scripts/analysis/analyze_charging_scenarios.py`

### 9.6 Polityka „advise-only” i komunikat dla użytkownika (MVP)

**Stanowisko produktu (do umieszczenia w UI i w docs obrony):**

> Mój system na razie tylko doradza i wyświetla powiadomienia na dashboardzie. Pokazuje, ile BYŚMY zaoszczędzili, gdybyśmy włączyli automatykę. Dopiero gdy po roku testów upewnię się, że algorytm się nie myli, udostępnię przycisk do fizycznego sterowania falownikiem.

**Wymagania UI (MVP):**

1. **Banner / karta stała** na ekranie Bateria (i skrót na Home): powyższy komunikat (skrócona wersja + „Dowiedz się więcej”).
2. **Powiadomienia push** z sugestiami zarządzania baterią i zmagazynowaną energią (okno taniej strefy, unikaj ładowania gdy jutro dużo PV, rezerwa SoC przed szczytem).
3. **Licznik kontrfaktyczny** `shadow_savings_pln` (dzień / miesiąc / YTD): różnica między kosztem faktycznym a kosztem przy wykonanym planie doradczym.
4. Przycisk „Steruj falownikiem” — **niedostępny** (disabled + tooltip z §9.6); brak wywołań API sterujących.

**Dlaczego nie pełna automatyka „na teraz” (punkty do ekranu „Dowiedz się więcej”):**

- Ryzyko kosztowe przy błędzie algorytmu (ładowanie w droższej strefie, zbędny import).
- Limit i niestabilność API FoxESS; brak dojrzałego OAuth sterowania w produkcie.
- Konieczność zebrania sezonu zimowego + letniego pod walidację shadow vs reality.
- Odpowiedzialność użytkownika / bezpieczeństwo instalacji (opt-in dopiero po dowodach).

---

## 10. Kontekst domowy

### 10.1 Kalendarz kontekstowy

- Wakacje, urodziny, „przetwory”, ferie, **dzień prania / suszenia**, posiłki AGD
- Tabela `household_events` (data, typ, wpływ: ↑zużycie / ↓zużycie / tryb_ferie)
- Żywy log → [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md) · reguła FC → [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md)

**Kalibracja typów (żywe pomiary Fox → reguły sugestii T4.9):**

| Typ | Case | Okno | Load w oknie | Peak | Reguła (szkic) |
|-----|------|------|-------------:|-----:|----------------|
| `przetwory` | **11.10.2026** buraki 1 porcja (3 kg buraków · 1,5 kg cebuli · 1,5 kg papryki) | ~13:00–17:40 (~4,7 h) | **~10,4 kWh** | ~5,6 kW | `impact=up` · planuj ~**10 kWh** / 4–5 h w ciągu dnia (najlepiej gdy PV); SoC −25 pp w case |
| `przetwory` → **nast. dzień roboczy** | **12.10.2026** po nd. przetwory: SoC **38%** @20:15 → **28%** @22:38; **brak na śniadanie** | noc + **05–08** | bojler **0,42** · bufor **0,58** · śniadanie **1,25** (razem **~2,3 kWh**) | 2,4 / 2,6 / 2,1 | Gate **SoC &lt;30% @~22** gdy jutro robocze → **`BUFOR RANO`** ~15 min; kwoty w env `BATTERY_MORNING_*_KWH` |
| `grzejnik_lazienka` | **noc 12→13.10.2026** suszenie ręczników całą noc | **22:00–07:00** (ciągły) | **+0,5–1,0 kWh** (szacunek 40–100 W; baseline Fox ~0,17 kW — trudny do wyodrębnienia) | niski, stały | `impact=up` · przy evencie w kalendarzu **dodaj** do budżetu nocy przed tanim FC; **nie** polegać tylko na SoC ≥30% |
| `podlogowka` | zima / chłodna jesień — cykle bufora ciepła (kalibracja **0,58 kWh**/cykl z 12–13.10; case **14.10** ~0,9 kWh przy Tnoc≲2°C) | **22:00–07:00** | **T×cykle:** T≥10→0 · 6–10→1× · 3–6→1,5× · 0–3→2× · −3–0→2,5× · &lt;−3→3× (`estimate_floor_heating_night_kwh`) | niski–średni, cykliczny | `impact=up` · event w kalendarzu → doradca **sam** liczy E_noc z Tśr jutra + cel SoC@22 (`suggested_soc_at_22_for_night_kwh`); dłuższy FC gdy &gt;1 cykl · aliasy: `ogrzewanie_podlogowe` |
| `sniadanie` | **13.10.2026** jajecznica + kawiarka na indukcji + czajnik (herbata) | ~07:08–08:20 | **~1,3–1,5 kWh** (12.10: **1,25**) | **2,2 / 1,5 / 3,8** kW | `impact=up` · planuj **~1,3 kWh** przed PV; pik **~3,8 kW** = czajnik+indukcja równolegle (nie bojler) · późne `sniadanie` (~09) **nie** zmniejsza budżetu nocy przy zimnie — liczy się bufor do pierwszej sensownej PV (~8–9) |
| `sniadanie` | **17.10.2026** jajka na twardo + kawa na indukcji + czajnik | **10:42–10:52** | rząd **~0,5 kWh** z próbek co ~5 min (pik mógł być krótszy niż slot) | **5,1 kW** @10:42, potem **~0,9 kW** | lżejszy niż plan ikony **1,4 kWh** · PV **~3,9 kW** · SoC **67%** · sieć **~0** · nie zmieniaj budżetu ikony |
| `zmywarka` | **14.10** start ~10:00 SoC **~12%** (słabe PV) · **16.10** cykl ~2 h, koniec **~13:35** przy PV **~4 kW** / SoC **99%** · **17.10** start **11:28–11:32**, grzanie **11:32–11:46** i znów **12:08** | cykl **~1–2 h** | typowo **~1–1,5 kWh**/cykl · **17.10** cykl otwarty @12:17, bez sumy | **~1,5–3 kW** · **17.10 ~2,1–2,2 kW** | `impact=up` · **nie** w drogim **6–13** przy pustej baterii / ciemnym dniu · przy Accu **jasny/mix** + SoC wysoki → **szczyt PV (11–15)** OK (case **16.10** bez importu) · inaczej tania **13–15** / po **22** · **17.10** SoC **100%** od **11:50**, eksport **~4 kW** |
| `pranie` | **16.10.2026** **2×** program po **~2,5 h**, jedno po drugim (rano→południe) | **~2,5 h**/cykl | ciągły load μ **~1–1,5 kW** w oknie prania (dom+AGD); godz. load **11–12** Fox **~1,4–1,5 kWh** | **~2–3 kW** (piki z innym AGD) | `impact=up` · **najlepiej dzień Accu jasny/RF + ENS ≳18** · start gdy PV już sensowne (**≳1–2 kW**, typowo po **~9**) · 2 cykle z rzędu OK jeśli SoC rośnie / bateria pełna · **nie** planować na CS4/pochmurno rano |
| `suszarka` | **16.10.2026** start **~16:10**, finisz **~17:40** (po 2× praniu) | **~1,5 h** | Fox **16:10–17:40** load **~1,2 kWh** · SoC **98→94** · import **~0** | ciągły **~0,6–0,8 kW** (dom+suszarka) | `impact=up` · start **po praniu**, gdy PV jeszcze jest albo SoC **≳80%** · po **15–16** PV spada → zejdzie z **baterii**; kalibracja EOD: **~1,2 kWh**/cykl (nie 2–4) przy wysokim SoC |
| `chleb` | **16.10.2026** maszynka Lidl · **~20 min do końca @13:35** (w tle zmywarka/obiad) | cykl pieczenia **~2–3 h** (finisz krótki) | niski–średni ciągły + finisz | **≲1–2 kW** (szacunek) | `impact=up` (lekki) · można równolegle z `zmywarka` / `obiad` przy PV **≳3–4 kW** · nie wymaga osobnego FC |
| `piekarnik` | kura / pieczeń — osobno od maszynki `chleb` | **~1–1,5 h** | szacunek **~2 kWh** (piekarnik ~2 kW) | **~2–2,5 kW** | `impact=up` · złoty stopień skali · najlepiej w szczycie PV · nie mieszać budżetu z `chleb` (~0,8 kWh) |
| `odkurzacz` | Dreamy, jedno przejście + ładowanie | **~1 h** | szacunek **~0,2 kWh** (brak pomiaru Fox) | niski | `impact=up` · zielony stopień |
| `mac_mini` | dzień pracy przy biurku · **17.10** czuwanie cały czas, obudzony kilka minut koło południa | **~8–10 h** (ikona) | szacunek **~0,2 kWh** za dzień pracy (~20 W) · czuwanie już w tle domu **~0,20 kW**, kilka minut jawy **nie do odjęcia** | niski | `impact=up` · zielony stopień · czuwania nie doliczać drugi raz |
| `macbook` | MacBook Pro, ładowarka **140 W** przez **8 h** pracy | **8 h** | **1,12 kWh** (140 W × 8 h) | **140 W** | `impact=up` · zielony stopień, blisko zmywarki · to górna granica, gdy ładowarka jest obciążona przez cały czas |
| `obiad` / `indukcja` | **16.10.2026** gotowanie + kawa na indukcji **@13:35** (równolegle z finiszem zmywarki/chleba) | **~15–40 min** | w pakiecie ze zmywarką: load chwilowy **2–3,9 kW** @13:28–13:51 | **~2–4 kW** | `impact=up` · krótkie piki · przy SoC **~100%** + PV **~4 kW** cały pakiet **bez importu** (case **16.10**) · w drogiej strefie bez PV → zjada SoC szybko |
| `kolacja` | **16.10.2026** lekka indukcja **~30 min** (Fox **~0,73 kWh**) — case „tylko gotowanie”; typowo też czajnik / piekarnik (parówki, frytki) jak śniadanie | **~17:45–18:15** (przykład) | **plan produktowy ~1,3–1,4 kWh** (= `sniadanie`); lekki case **~0,7** | peak **~3–4 kW** | `impact=up` · **bez PV** — z baterii · budżet **jak śniadanie** (ciepłe + herbata/czajnik ± piekarnik) · nie łączyć z pustą baterią przed szczytem drogi 17–22 · ostrzeż o SoC @22 |
| meta: `force_charge` / stop | **13→14.10** plan 65%@22:35 → Fox **nie uciął** → **80%** · **15→16.10** zapomniane wyłączenie **63%→100%** (~22:01–22:28, **~3,7–3,8 kWh**) przy Accu **jasny** | tania **22:00+** | **+50 pp / ~30 min** ≈ **~5 kWh** @**10–11 kW** | **~9–12 kW** grid | kalendarz/apka: **alarm „wyłącz FC”** o zaplanowanym końcu · przy sugestii **POMIŃ** (Accu jasny / ENS ≳12–18 i SoC ≳50–60%) **nie** startować FC „na zapas” · case **15→16**: FC zbędne, rano i tak min **~30%** przed PV |

**17.10 ok. 12:12–12:17 — wiertarka** (wieszanie; lampa LED **bez** kWh): dom **3,50** potem **4,33 kW** przy grzaniu zmywarki **~2,2 kW**. Nadwyżka **~1,3** potem **~2,1 kW** to wiertarka. Nie ikona kalendarza — wpis `wiertarka` w `household_events` ma samą notatkę, bez kWh.

**Pakiet „dzień prania” (kalibracja 16.10):**

```text
JEŚLI  w kalendarzu dziś: pranie (≥1) [+ opcjonalnie zmywarka / suszarka / obiad]
  ORAZ  Accu reżim jasny|mix→RF  (albo ENS jutro/dziś ≳ 18 kWh)
TO  sugeruj okno AGD w szczycie PV (ok. 11–15); FC nocy poprzedniej POMIŃ jeśli SoC@22 ≳ 50–60%
    suszarkę planuj zaraz po praniu albo gdy SoC wysoki — nie na szczyt drogi 17–22 przy pustej baterii

JEŚLI  pranie|suszarka na dzień Accu pochmurny→CS4 / słabe PV
TO  ostrzeż: ryzyko importu; lepiej przesunąć albo noc G12w (22–6) dla suszarki
```

Fox **16.10** (do ~15:57, przed końcem suszarki): generation **~20,4** · loads **~14,8** · feedin **~9,6** · gridConsumption **~0,4** · SoC popołudniu **98–99%**. Closeout suszarki — uzupełnić EOD w logu baterii.

**Budżet taniej taryfy → rano (nauka, G12w 22–6):**

```text
E_noc ≈ bojler(~0,4) + sniadanie(~1,3)
       + grzejnik_lazienka(0,5–1,0 jeśli event)
       + podlogowka(T×cykle ~0,58 kWh)  LUB  bufor_ciepła(~0,6 przy Tnoc≲5–6°C bez eventu)
ΔSoC_pp ≈ E_noc / 0,104          # BATTERY_CAPACITY ≈ 10,36 kWh
cel_SoC@22 ≥ minSoc(10%) + ΔSoC + margines(~8 pp)
```

Przy evencie `podlogowka` próg BUFOR RANO = **cel SoC@22 z budżetu** (nie sztywne 30%).

Case **12→13.10:** SoC **50% @22** (powyżej progu BUFOR RANO **30%**) → sugestia „starczy”; ex post **10% @07**, śniadanie z sieci. Powód: wieczór już **86→50%**, Tnoc **~5°C** → bufor, bojler **~02:52**, **grzejnik łazienkowy**, potem śniadanie indukcja+czajnik. **50% @22 ≈ budżet nocy bez śniadania.**

Case **15→16.10 (jasny dzień + pomyłka FC):** SoC **63% @22** → FC do **100%** (~4 kWh taniej nocy) przy Accu **9/11%** / ENS **~22** — **niepotrzebne** kosztowo; rano min **~29–30%** przed PV i tak bez luki sieci. Wniosek kalendarza: event `pranie` na jutro **nie** wymusza FC, jeśli prognoza PV wysoka i SoC@22 już ≥~50%.

### 10.2 Strategia sezonowa

| Sezon | Cel | Dane |
|-------|-----|------|
| Lato | Klimatyzacja vs bateria / autokonsumpcja PV | loads + PV + SoC |
| Zima | Arbitraż G12w + ciepło (podłogówka) przy zachowaniu Wi‑Fi / standby | zone + bateria |

### 10.3 Wsparcie behawioralne (MVP: push + dashboard)

- **Push (MVP):** sugestie baterii / magazynu — tania strefa G12w, nocne ładowanie, rozładowanie przed szczytem, „jutro dużo PV — nie ładuj z sieci”
- Push (faza 2): „Włącz tryb Ferie” / „Standby przed wyjazdem”
- Wszystkie alerty są **doradcze**; nie zmieniają WorkMode falownika (patrz §9.6)

### 10.4 Formuła klimatyzacji (T4.5)

Parametry: moc AC [kW], SoC_now, SoC_min_morning, pojemność, sprawność, **nocny load domu** (domyślnie 0,55 kW).

Do **18:00** zakładamy, że PV jeszcze pokrywa bazę. Od 18:00 (albo od „teraz”, jeśli później) bateria płaci za resztę nocy do **6:00**:

```
energia_dostępna = (SoC_now − SoC_min_morning)/100 × pojemność × sprawność
energia_dom_noc = load_noc × godziny_do_6:00
czas_AC_h = max(0, energia_dostępna − energia_dom_noc) / moc_AC
wyłącz_o = start_nocy_baterii + czas_AC_h   # nie później niż 6:00
```

UI (karta **tylko** gdy kalendarz ma dziś `klimatyzacja` / `upał`): **„Wyłącz AC o HH:MM”** — starczy do rana, pomieszczenia zostają schłodzone. Apka nie gasi klimatyzacji (§9.6).

---

## 11. Dodatkowe moduły — z danych projektu

| Moduł | Skąd | Wartość |
|-------|------|---------|
| **Prognoza PV dziś/jutro** | RF + Open-Meteo + `forecast_history` | rdzeń produktu |
| **Closeout vs app Fox** | walidacja PVE | zaufanie do modelu |
| **Notatki pogodowe** | `weather_notes` | jakość dni „dziwnych” |
| **Depozyt net-billing / RCEm** | `rcem_prices`, `prosumer_deposit` | „ile kasy w drodze” |
| **Jakość danych / luki IoT** | EDA, `FOXESS_RELIABLE_START` | komunikaty „brak danych” |
| **Porównanie modeli pogody** | ICON vs UKMO (analizy) | zaawansowane / settings |
| **Raport miesięczny PDF** | agregacja foxess + bills | na koniec miesiąca |
| **Alerty limitu API Fox** | 40402 w fetch | ops w telefonie |

**Priorytet MVP mobilnego:** Sync + Symulator + ROI + Prognoza PV + **doradczy optymalizator baterii** (plan + push + shadow savings + banner „brak automatyki”) + komunikat advise-only. Kalendarz kontekstowy i sterowanie fizyczne — później.

---

## 12. Interfejs API HTTP (FastAPI)

Warstwa HTTP jest **jedynym kontraktem** między aplikacją Ionic a istniejącym kodem Pythona (`src/*`, `mlops/*`, model `.joblib`). Implementacja: **FastAPI** + Uvicorn, dokumentacja interaktywna OpenAPI pod `/docs` (Swagger) i `/redoc`.

Szczegółowe zadania: [ZADANIA_IMPLEMENTACJA_MOBILNA.md](ZADANIA_IMPLEMENTACJA_MOBILNA.md) — sekcja **Faza 0.2 / Faza API**.

### 12.1 Zasady kontraktu

| Zasada | Opis |
|--------|------|
| Wersjonowanie | Prefiks **`/api/v1/...`** (breaking changes → `/api/v2`) |
| Format | JSON (`application/json`), daty ISO-8601 (`YYYY-MM-DD` / UTC ISO) |
| Auth | `Authorization: Bearer <JWT>` na endpointach chronionych; `/health`, `/docs` publiczne |
| Błędy | Jednolity shape: `{ "detail": "...", "code": "FOXESS_RATE_LIMIT", "request_id": "..." }` |
| Idempotencja | Sync Fox z tym samym zakresem dat = upsert (bez duplikatów) |
| PII | Odpowiedzi overview **bez** prawdziwego SN / nazwiska — placeholder `REDACTED` |
| Owinięcie | Endpointy wołają istniejące funkcje; **bez** przepisywania ML do TypeScript |

### 12.2 Struktura pakietu `api/`

```
api/
  __init__.py
  main.py                 # FastAPI app, CORS, lifespan (load model)
  deps.py                 # DB session, current_user, settings
  config.py               # pydantic-settings z env
  schemas/                # Pydantic request/response
    auth.py
    foxess.py
    forecast.py
    tariff.py
    simulate.py
    roi.py
    battery.py
    household.py
    deposit.py
    common.py             # ErrorResponse, HealthResponse
  routers/
    health.py
    auth.py
    foxess.py
    forecast.py
    tariff.py
    simulate.py
    roi.py
    battery.py
    household.py
    deposit.py
  services/               # cienkie adaptery → src.*
    foxess_sync.py
    forecast_ml.py
    bill_simulator.py
    roi_service.py
    battery_planner.py
  middleware/
    request_id.py
```

### 12.3 Katalog endpointów (`/api/v1`)

#### Health / meta

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/health` | nie | Liveness: status, wersja API, ping DB |
| `GET` | `/ready` | nie | Readiness: DB + plik modelu `.joblib` |

#### Auth

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `POST` | `/api/v1/auth/login` | nie | Login → access + refresh JWT |
| `POST` | `/api/v1/auth/refresh` | refresh | Nowy access token |
| `POST` | `/api/v1/auth/logout` | tak | Unieważnienie refresh (opcjonalnie) |
| `POST` | `/api/v1/auth/fox/callback` | tak* | Callback OAuth Fox (jeśli dostępne) |
| `POST` | `/api/v1/auth/fox/link` | tak | Powiązanie zaszyfrowanego API key Fox |
| `DELETE` | `/api/v1/auth/fox/link` | tak | Odłączenie konta Fox |

#### FoxESS (dane)

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `POST` | `/api/v1/foxess/sync` | tak | Body: `{ "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" }` → sync historii |
| `GET` | `/api/v1/foxess/overview` | tak | Query: `day=` → KPI: PV, SoC, import, export, `fetched_at` |
| `GET` | `/api/v1/foxess/timeseries` | tak | Query: `day=`, `variables=` (opcjonalnie) → punkty do wykresów |

#### Prognoza ML

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/api/v1/forecast/hourly` | tak | Query: `day=` → szereg godzinowy kWh + suma dnia |
| `GET` | `/api/v1/forecast/validation` | tak | Query: `day=` → prognoza vs actual / closeout (jeśli jest) |

#### Taryfa i symulacja rachunku

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/api/v1/tariff/rates` | tak | Aktualne / ostatnie stawki użytkownika |
| `POST` | `/api/v1/tariff/rates` | tak | Zapis stawek z faktury Tauron |
| `POST` | `/api/v1/simulate/bill` | tak | Body: okres + opcjonalne override stawek → `cost_no_pv`, `cost_with_pv`, `savings_pln`, kWh |

#### ROI

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/api/v1/roi/assumptions` | tak | CAPEX / OPEX / inflacja |
| `PUT` | `/api/v1/roi/assumptions` | tak | Zapis założeń |
| `POST` | `/api/v1/roi/calculate` | tak | Payback, ROI %, seria skumulowanych oszczędności |

#### Bateria (advise-only w MVP)

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/api/v1/battery/settings` | tak | SoC min, sprawność, sezon, ceny z1/z2 |
| `PUT` | `/api/v1/battery/settings` | tak | Zapis ustawień |
| `GET` | `/api/v1/battery/plan` | tak | Query: `date=` → okna G12w + plan SoC 24h (**bez** komend do falownika) |
| `GET` | `/api/v1/battery/night-charge-advice` | tak | Sugestia ładowania nocnego + uzasadnienie PL |
| `GET` | `/api/v1/battery/shadow-savings` | tak | Query: `from=`, `to=` → `shadow_savings_pln` (kontrfakt: gdyby wykonano plan) |
| `GET` | `/api/v1/battery/policy` | tak | Stały tekst / kod polityki advise-only (§9.6) |
| `GET` | `/api/v1/battery/ac-runtime` | tak | `suggested_off_at`, nocny kWh, `show_card` (kalendarz klimatyzacja) |
| `POST` | `/api/v1/battery/ac-runtime` | tak | Body: opcjonalna moc AC → to samo co GET |
| `GET` | `/api/v1/notifications` | tak | Lista sugestii (in-app feed na dashboard) |
| `POST` | `/api/v1/notifications/push-token` | tak | Rejestracja FCM/APNs token |
| — | ~~`POST /battery/control`~~ | — | **Celowo nie istnieje w MVP** |

#### Dom / depozyt / notatki

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| `GET` | `/api/v1/household/events` | tak | Lista wydarzeń (zakres dat) |
| `POST` | `/api/v1/household/events` | tak | Dodanie wydarzenia |
| `DELETE` | `/api/v1/household/events/{id}` | tak | Usunięcie |
| `GET` | `/api/v1/deposit/summary` | tak | Wolny depozyt + pending RCEm |
| `GET` | `/api/v1/weather-notes` | tak | Lista notatek |
| `POST` | `/api/v1/weather-notes` | tak | Nowa notatka (port ze Streamlit) |

### 12.4 Przykładowe kontrakty (Pydantic)

**`GET /api/v1/foxess/overview?day=2026-07-25`**

```json
{
  "day": "2026-07-25",
  "pv_kwh": 34.4,
  "soc_percent": 62.0,
  "grid_import_kwh": 1.2,
  "grid_export_kwh": 18.5,
  "load_kwh": 12.0,
  "device_sn_display": "REDACTED",
  "last_synced_at": "2026-07-25T16:00:46Z"
}
```

**`POST /api/v1/simulate/bill`**

```json
{
  "period_start": "2026-06-01",
  "period_end": "2026-06-30",
  "vat_mode": "gross",
  "rates_override": null
}
```

```json
{
  "cost_no_pv_pln": 420.50,
  "cost_with_pv_pln": 15.94,
  "savings_pln": 404.56,
  "import_kwh": 36.0,
  "export_kwh": 514.0,
  "self_consumed_kwh": 280.0,
  "deposit_credit_pln": 140.42
}
```

### 12.5 Mapowanie FastAPI → kod istniejący

| Router / service | Moduł źródłowy |
|------------------|----------------|
| `services/foxess_sync.py` | `src/data/foxess_fetch_all.py`, `src/data/foxess_api.py` |
| `services/forecast_ml.py` | `src/models/pv_hourly_predictor.py`, features, `models/pv_hourly_model.joblib` |
| `services/bill_simulator.py` | `src/financial/roi_calculator.py`, `prosumer_deposit.py` |
| `services/roi_service.py` | `FinancialAnalyzer` |
| `services/battery_planner.py` | `src/optimization/g12w_tariff.py` |
| weather notes | `src/data/weather_notes.py` |
| RCEm / depozyt | `src/data/rcem.py`, `src/financial/prosumer_deposit.py` |

### 12.6 Uruchomienie (docelowe)

```bash
# w Docker
docker compose up db api

# lokalnie (dev)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
# OpenAPI: http://localhost:8000/docs
```

Ionic (dev) wskazuje `API_BASE_URL=http://<LAN-IP>:8000`.

---

## 13. Model danych (rozszerzenia)

Obok obecnego schematu:

- `app_users`, `user_secrets` (encrypted Fox token)
- `user_tariff_overrides`
- `household_events`
- `roi_assumptions` (CAPEX, OPEX)
- `battery_strategy_settings`
- `notifications` (feed sugestii advise-only)
- `push_subscriptions`
- `advice_events` (log pod walidację roczną shadow vs reality)

Migracja: Alembic / SQL skrypt z `database_schema.sql` → Postgres.

---

## 14. Bezpieczeństwo i prywatność

- Brak PPE / adresu / nazwiska w logach UI
- SN falownika tylko w vault
- HTTPS, PKCE, short-lived access tokens
- **MVP: brak endpointów sterujących falownikiem**; sync = read-only (+ przyszły vault klucza)
- Sterowanie fizyczne (ForceCharge) — dopiero po okresie walidacji ~1 rok, osobna zgoda opt-in (poza MVP)

---

## 15. Fazy wdrożenia (orientacyjnie)

| Faza | Zakres | Czas |
|------|--------|------|
| 0 | Spike OAuth Fox + Docker DB/API skeleton | 1–2 tyg. |
| 1 | Ionic shell + Solar Graphite + sync overview + prognoza | 2–3 tyg. |
| 2 | Symulator rachunków + formularz stawek | 2 tyg. |
| 3 | ROI | 1 tyg. |
| 4 | Optymalizator baterii **doradczy** (plan + banner §9.6 + shadow savings) + **push sugestii (MVP)** | 2–3 tyg. |
| 5 | ML decyzja ładowania nocnego (nadal advise-only) + kalendarz | 2 tyg. |
| 6 | Sterowanie Fox — **po ~roku testów**, za zgodą | poza MVP |

Szczegółowa lista zadań: [ZADANIA_IMPLEMENTACJA_MOBILNA.md](ZADANIA_IMPLEMENTACJA_MOBILNA.md).

---

## 16. Kryteria sukcesu MVP

- Użytkownik loguje się i widzi dzisiejszą produkcję / SoC z bazy po sync.
- Symulator pokazuje 2 słupki + oszczędność na ≥1 pełnym miesiącu danych.
- ROI zwraca payback z CAPEX użytkownika.
- Plan baterii na jutro uwzględnia okna G12w (i opcjonalnie prognozę PV).
- **Banner advise-only** (§9.6) widoczny; brak możliwości fizycznego sterowania.
- **Push / feed sugestii** zarządzania baterią i magazynem działa (lub co najmniej in-app na dashboardzie).
- Widoczny licznik **shadow savings** („ile BYŚMY zaoszczędzili przy automatyce”).
- UI zgodne z Solar Graphite; brak elementów brandingu FoxESS.

---

## 17. Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Brak OAuth u Fox | Własne OAuth + API key vault |
| Limit API Fox (40402) | Cache DB, sync rzadziej, worker z backoff |
| SQLite vs Postgres | Docker Postgres + migracja |
| Sterowanie baterią = ryzyko kosztowe / błędny algorytm | **MVP tylko doradztwo + shadow savings**; fizyczne sterowanie po ~roku walidacji |
| Użytkownik oczekuje „automatu od razu” | Stały komunikat UI (§9.6) + transparentny licznik hipotetycznych oszczędności |
| Model ML „nie na telefonie” | Inference tylko na backendzie |
| Push (FCM) złożoność na Android | MVP: in-app feed + opcjonalnie FCM; nie blokować reszty MVP |

---

## 18. Nawiązanie do dokumentacji istniejącej

- Założenia ML: [03_ZALOZENIA_I_DECYZJE.md](03_ZALOZENIA_I_DECYZJE.md)
- FoxESS: [FOXESS_KROK_PO_KROKU.md](FOXESS_KROK_PO_KROKU.md)
- API key dziś: [API_CONFIGURATION.md](API_CONFIGURATION.md)
- G12w: `src/optimization/g12w_tariff.py`
- Zadania implementacji: [ZADANIA_IMPLEMENTACJA_MOBILNA.md](ZADANIA_IMPLEMENTACJA_MOBILNA.md)
