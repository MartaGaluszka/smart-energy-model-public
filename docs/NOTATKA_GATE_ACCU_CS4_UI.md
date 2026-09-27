# Gate — Accu → CS4 w UI (bez ICON-only)

**Status:** **PROPOZYCJA** (do decyzji — nie wdrożone)  
**Data spisania:** 2026-09-26  
**Poprzedni gate:** [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) (01.09) — **REJECT** ICON≥30%→CS4 · **ACCEPT** ENS primary  
**Dowód wrzesień:** analiza 1–25.09 (canvas *September-2026-Models-x-Weather*) · closeouty `forecast_validation.csv`  
**Paper Accu (reguła reżimu):** paper-trade Accu (tylko repo prywatne)

---

## 1. Problem

Launchd / app zawsze pokazują **ENS (RF16 × ICON+UKMO)**.  
CS4 (19 cech: 16 + low/mid + clearness) jest **shadow** — dobre na szare / mokre dni, ale użytkownik widzi ENS nawet gdy Accu mówi „ciemno”.

**Przykład 25.09:** Accu **2 / 89% / 3,3 mm** → paper **CS4**.  
Fox **7,8** · CS4 daily **7,55 (−3%)** · ENS **~14 (+79%)**.  
Reżim trafiony, model CS4 trafiony, UI nie.

Poprzedni auto-routing po **ICON cloud** = REJECT (ICON za często „pochmurny” na jasne dni).

---

## 2. Hipoteza gate’u (ta propozycja)

```text
JEŚLI Accu (dziś-na-dziś, karta ≤ ~08:00 lub ostatnia available):
     Lumen ≤ 4
  LUB cloud ≥ 70%
  LUB opad ≥ 2 mm
  LUB burze ≥ 40%
→ UI / API „główna suma dnia” = CS4 (shadow CSV już w launchd)

INACZEJ (jasny / mix / brak Accu):
→ zostaje ENS (primary bez zmian)

NIGDY nie sterować pickiem samym ICON cloud.
Launchd zapis ENS do pv_forecast.csv — bez zmian (audit / baseline).
```

To jest **to samo drzewo co paper Accu**, tylko z celem **pokazać CS4 w produkcie**, nie tylko w notatce.

---

## 3. Zakres wdrożenia (fazy)

### Faza 0 — paper-trade only ← **tu trzymamy teraz (rekomendacja 26.09)**

| | |
|--|--|
| **Gdzie** | paper-trade Accu + skrypt analizy (tylko repo prywatne) |
| **Co** | Reguła Accu→CS4 / mix→RF **bez zmiany UI i launchd**; po closeoucie: pick vs Fox, false positive (clearing), Fox ≲ 15 |
| **Po co** | Domknąć n≥10 jakościowych (nie tylko Accu-pochmurnych „z kartą”) · zebrać **X–XII** zanim Faza A |
| **Dodatek do logu** | kolumna / uwaga: `fox_bucket` (&lt;15 vs ≥15) · `cs4_ok?` · `watch_mix` (MB clearing) |

Dopóki zima nie ma serii closeoutów Accu+CS4: **nie włączaj Fazy A w prod**. Paper = miejsce prawdy dla gate’u.

### Faza A — UI overlay (niskie ryzyko) ← dopiero po zimowym REVIEW

| | |
|--|--|
| **Co** | Home / prognoza: gdy reżim Accu = pochmurny → **wyróżniona suma CS4** (+ badge „reżim pochmurny · CS4”); ENS zostaje w drugim wierszu / tooltip |
| **Czego nie** | Nie nadpisujemy `pv_forecast.csv`, nie zmieniamy baterii/planu 24h na CS4 w v1 |
| **Źródło Accu** | `weather_notes` (source AccuWeather) — jak paper; brak karty → ENS only |
| **Źródło CS4** | `pv_forecast_cs4.csv` / kolumny closeout już istnieją |
| **Feature flag** | np. `ACCU_CS4_UI=1` w `.env` (domyślnie OFF do ACCEPT) |

### Faza B — API kontrakt

```text
GET /forecast/daily (lub rozszerzenie istniejącego):
  primary_kwh      = ENS (zawsze)
  display_kwh      = CS4 | ENS   # według reguły Accu
  display_model    = "cs4" | "ensemble"
  regime           = "pochmurny" | "mix" | "jasny" | "unknown"
  accu             = { lumen, cloud_pct, precip_mm } | null
```

Mobile czyta `display_*`; diagnostyka nadal ma ENS.

### Faza C — (opcjonalnie, osobny gate) primary launchd

Tylko po **ACCEPT** Fazy A+B **i** spełnieniu metryk poniżej.  
Nadal **nie** ICON-only. Możliwe: `routing_pick.csv` z Accu → wybór pliku do „karty dnia”, ENS CSV nienaruszony.

---

## 4b. Kiedy to się sprawdza (live dual 27.07–25.09, n=62 ENS+CS4)

**CS4 pomaga**, gdy dzień jest **naprawdę ciemny w kWh**, nie tylko „cloud % wysoki”:

| Warunek | n | ENS MAPE | CS4 MAPE | CS4 wygrywa |
|---------|--:|---------:|---------:|------------:|
| Accu **pochmurny** | 11 | 34% | **23%** | 6/11 |
| Accu pochmurny **i Fox &lt; 15** | 7 | ~45%* | niżej | **6/7** |
| Accu pochmurny **i Fox ≥ 15** | 4 | ~7–17% | gorzej | **0/4** (m.in. 12–13.09 clearing) |
| OM cloud ≥85% **i Fox &lt; 15** | 11 | 53% | **32%** | 9/11 |
| OM cloud ≥85% **i Fox ≥ 20** | 5 | 18% | 22% | 2/5 — raczej ENS |
| Accu **mix / jasny** | 17 | 9–13% | wyżej | prawie zawsze ENS |
| Fox **≥ 25** (słońce) | 35 | 12% | 13% | 11/35 — default ENS |

\*w tym outliery 11.09 / 25.08.

**Heurystyka operacyjna (silniejsza niż sam Accu):**

```text
Accu pochmurny (Lumen≤4 / cloud≥70 / mm≥2)
  ORAZ oczekiwany dzień niski (ENS lub CS4 lub ½ oneshot ≲ 15 kWh)
→ display CS4

Accu pochmurny ALE prognoza / MB mówi clearing i suma ≳ 18–20 kWh
→ ENS + badge „watch mix” (nie wymuszaj CS4)
```

Czysty Accu bez progu kWh łapie false positive (12–13.09: Accu CS4, ENS ~2% APE).

---

## 4c. Zima (XI–II) — co wiemy / czego nie

| | |
|--|--|
| **Live dual ENS vs CS4 zimą** | **brak** — para closeoutów od **27.07.2026** (lato/jesień) |
| **Accu w DB** | tylko **VII–IX 2026** — zima bez kart Accu do paper |
| **Cechy CS4** | low/mid/clearness — zimą częściej „szaro”, więc **hipoteza sprzyja CS4**, ale nieudowodniona live |
| **Bateria zima** | osobny tor ([`PLAN_BATERIA_JESIEN_ZIMA_2026.md`](PLAN_BATERIA_JESIEN_ZIMA_2026.md): rezerwa 40%, FC od T+PV) — **nie mylić** z routingiem kWh |
| **Ryzyko** | zimą ENS bywa konserwatywny; CS4 może **niedoszacować** jeszcze mocniej na krótkim dniu / śniegu — potrzebny **shadow-only XI–XII** zanim Faza C |

**Plan zima (propozycja):**

1. X–XI: Faza A (UI) tylko gdy Accu pochmurny **i** display/ENS ≲ 15 kWh (reguła §4b).  
2. Zbierać Accu daily + closeout CS4 przez **≥10 dni XI–XII** z Fox &lt; 15.  
3. Osobny mini-gate **„zima Accu→CS4”** — nie dziedziczyć ACCEPT z września automatycznie.  
4. Weekly train i tak odświeża CS4 co niedzielę — okna zimowe wejdą do wag expanding.

---

### Próbka (wymagana przed ACCEPT Fazy A→prod ON)

| Kryterium | Próg |
|-----------|------|
| Mokre / Accu-pochmurne closeouty z kartą Accu + CS4 daily | **n ≥ 10** |
| Okno | od dual CS4 (ok. **27.07**) albo świeże **IX–X 2026** |
| Outliery typu **11.09** (Fox &lt; 5 kWh, APE &gt; 100%) | raportuj **osobno**; MAPE z i bez outliera |

### Metryki (na dniach Accu = pochmurny)

| Metryka | ACCEPT | REJECT |
|---------|--------|--------|
| MAPE **display** (CS4) vs MAPE **ENS** | display ≤ ENS **−2 pp** | display &gt; ENS |
| Dni z \|APE\| display &gt; 40% | nie więcej niż u ENS | wyraźnie więcej niż ENS |
| False positive Accu (CS4 gorszy o ≥10 pp, np. clearing 12–13.09) | ≤ **30%** dni Accu-pochmurnych | &gt; 40% |
| Dni Accu mix/jasny | display = ENS; nie psuć MAPE vs always-ENS o &gt; **1 pp** | degradacja &gt; 1 pp |

### Świadectwo wrzesień (1–25.09, wstępne — **jeszcze nie gate**)

| Slice | n | ENS MAPE | CS4 MAPE | Komentarz |
|-------|--:|---------:|---------:|-----------|
| Całość closeout | 25 | 22,4% | 20,0% | zawsze-CS4 lekko lepszy; nie cel |
| Accu pochmurny (paper) | 7 | 46,9% | 32,4% | CS4 pomaga; n&lt;10 |
| Accu pochmurny bez 11.09 | 6 | 25,6% | 16,4% | silny sygnał |
| OM „pochmurny” (szeroki) | 17 | 26,9% | 22,1% | CS4 bliżej, ale ENS wygrywa 9/17 — **nie** brać OM/ICON bucketu |
| Hybrid Accu→CS4 else ENS | 25 | — | **18,3%** (vs ENS 22,4%) | kierunek OK |
| Hybrid bez 11.09 | 24 | — | **13,7%** (vs ENS 16,0%) | kierunek OK |

**Werdykt na dziś:** **REVIEW** — zbierać do **n≥10** Accu-pochmurnych z pełnym closeoutem; Faza A można kodować za flagą OFF.

---

## 5. Guardraile (żeby nie powtórzyć ICON≥30%)

1. **Brak Accu → ENS.** Nie fallback do ICON cloud.
2. **MB / okno clearing:** jeśli MB meteogram = słońce PM przy Accu cloud ≥70 → UI badge **„watch mix”**, display może zostać ENS (opcja v1.1) albo CS4 + warning. Na 12–13.09 ENS był lepszy.
3. **Nie ruszać** `ENSEMBLE_PRIMARY=1` ani weekly train dual — CS4 i tak się trenuje w niedzielę.
4. **Audit:** każdy dzień z `display_model=cs4` logowany (advice_events / CSV) jak paper.
5. **Kill switch:** `ACCU_CS4_UI=0` wraca do samego ENS w UI w 1 restarcie.

---

## 6. Plan prac (szacunek)

| # | Task | Est. | Zależność |
|---|------|-----:|-----------|
| G0 | Checklist n Accu-pochmurnych + skrypt gate (reuse skryptu paper (prywatne)) | 1 h | — |
| G1 | Flaga + helper `accu_regime_for_day()` w API | 2 h | G0 |
| G2 | Endpoint / pole `display_kwh` + testy | 2–3 h | G1 |
| G3 | Mobile Home: suma + badge reżimu | 2–3 h | G2 |
| G4 | Notatka gate po n≥10 (ACCEPT/REJECT) | 1 h | live |
| G5 | (opcjonalnie) Faza C | osobny gate | ACCEPT G4 |

**Nie blokuje** jutrzejszego `train_dual_weekly.sh` — to osobna decyzja produktowa.

---

## 7. Decyzja (do odhaczenia)

- [ ] **REVIEW** — trzymamy ENS primary; paper Accu kontynuujemy; Faza A za flagą OFF OK do kodowania  
- [ ] **ACCEPT Faza A** — po n≥10 i metrykach §4; `ACCU_CS4_UI=1`  
- [ ] **REJECT** — jeśli na n≥10 CS4 nie bije ENS na Accu-pochmurnych o ≥2 pp  
- [ ] **Faza C** — dopiero osobnym gate’em po stabilnym A

**Rekomendacja 26.09:** odhaczyć **REVIEW** · **trzymać regułę w paper-trade** (Faza 0) · nie kodować UI do czasu serii X–XII / n jakościowych z Fox≲15. G0 = dopisać do paper logu Fox bucket + cs4_ok.

---

## 8. Linki

| | |
|--|--|
| Gate ICON/ENS 01.09 | [`NOTATKA_TEST_ROUTING_28-31_08.md`](NOTATKA_TEST_ROUTING_28-31_08.md) |
| Paper Accu RF↔CS4 | paper-trade Accu (tylko repo prywatne) |
| STATUS ML | [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) |
| Skrypt paper | tylko repo prywatne |
| Closeout CS4 | kolumny `predicted_*_cs4` w `forecast_validation.csv` |

---

*Propozycja spisana 2026-09-26 — do decyzji; bez zmiany prod do ACCEPT.*
