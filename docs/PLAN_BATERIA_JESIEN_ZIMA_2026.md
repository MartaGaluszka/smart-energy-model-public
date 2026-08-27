# Plan optymalizacji baterii — jesień / zima

**Data:** 2026-08-02  
**Źródło:** `foxess_data` + `foxess_report_daily` (IX.2025–II.2026) · doradca: `battery_advisor` / G12w  
**Pojemność:** ~10,36 kWh · dno sprzętowe SoC ~5–10%

Powiązane: [`PROJEKT_APLIKACJA_MOBILNA.md`](PROJEKT_APLIKACJA_MOBILNA.md) §9 · [`PLAN_T1_T2_LIPIEC_2026.md`](PLAN_T1_T2_LIPIEC_2026.md) · EA chmur (osobny wątek ML)

---

## Werdykt z danych (wrzesień → luty)

| Miesiąc | Noce z SoC ≤12% | Śr. min SoC noc | Śr. PV [kWh] | Śr. import sieci | Co widać |
|---------|----------------:|----------------:|-------------:|-----------------:|----------|
| **IX** | 37% | ~42% | 19 | 2,6 | jeszcze lato; część nocy pada |
| **X** | **77%** | ~18% | 13 | 6 | **klif** — traktować jak wczesną zimę |
| **XI** | 87% | ~12% | 8 | 19 | wieczór drenuje → pusto do rana |
| **XII** | **100%** | ~8% | 4 | 27 | bez nocnego ładowania bateria prawie martwa |
| **I** (od **7.01** FC nocny z Tauron) | ~4%* | ~48%* | 6 | ↑ (tani import nocny) | noc OK; dno wraca wieczorem |
| **II** | ~4% | ~51% | 10 | 26 | FC nocny z Tauron jak w I |

\*I: 1–6.01 jak grudzień (pusto); od **7.01** (potwierdzone operacyjnie) + luty: doładowanie baterii w nocy z sieci Tauron (ForceCharge / tanie okna G12w) — naprawia overnight.

**Główne awarie (nie błąd modelu PV):**
1. **Pusta noc (X–pocz. I, bez FC)** — rozładunek od ~15:00 → do 22:00 często ≤12% → rano drogi import.
2. **Grudzień bez FC** — za mało PV, max SoC ~24%, magazyn bezużyteczny.
3. **Eksport wczoraj → pusta noc** (IX–X) — nadwyżka poszła do sieci zamiast rezerwy.
4. **Po FC od 7.01 + luty** — noc pełna (ładowanie z Tauron w oknach nocnych), ale **do 18–21 znowu dno** (brak ochrony wieczornego SoC / słabe doładowanie 13–15).

---

## Cele optymalizacji

| Sezon | Cel biznesowy | Metryka sukcesu |
|-------|---------------|-----------------|
| **Jesień (IX–X)** | mniej pustych nocy bez zbędnego FC codziennie | % nocy ≤12% &lt; 40% (X obecnie 77%) |
| **Zima (XI–II)** | tani import nocny G12w zamiast drogiego 6–12; bateria żywa na szczyt wieczorny | import 6–12 ↓ (XII było ~7 kWh/d); SoC@16:00 ≥ 50% |

---

## Polityka proponowana

### Lato (V – ~15.09) — lekcja 25–26.08

Noc **25→26.08:** FC 22:00–22:30 **24% → 75%** (+51 pp / 30 min). 26.08 dach **~21 kWh**, bateria pełna od 12:38 → eksport. Pełnienie „pod deszcz jutro” **niepotrzebne**. VI–VIII 2026: para dni oba &lt; 8 kWh praktycznie tylko 10–11.06.

| Parametr | Propozycja | Uzasadnienie |
|----------|------------|--------------|
| Rezerwa / nocna podłoga | **20%** (`BATTERY_SOC_RESERVE_SUMMER`) | 24% na noc wystarczyło; 15% było za nisko vs praktyka |
| ForceCharge 22–6 | **nie** pełnić; krótki FC tylko gdy SoC **&lt; 20%** **i** jutro PV **≤ 10 kWh** | jutro do 10 kWh to nadal lato, nie zima |
| Jeśli już ładować | **max 15 min** / **+25 pp** SoC, nie do 75–100% | nawet przy jutrze ≤10 kWh; 30 min ≈ +50 pp |
| ForceCharge 13–15 | opcjonalnie | tanie G12w, nie krytyczne |

### A. Jesień (ok. 15.09 – 31.10)

| Parametr | Propozycja | Uzasadnienie |
|----------|------------|--------------|
| Tryb sezonu | **jesień** (dziś kod: lato do IX, zima od X) | IX już 37% pustych nocy |
| Rezerwa SoC | **20–25%** | mostek: lato 20% → zima 40% |
| Min SoC wieczór (alert 16:00) | **40–50%** | X: SoC@16~60 → SoC@22~40 → dużo crashy |
| ForceCharge 22–6 | **warunkowo**: gdy prognoza PV jutro **&lt; ~8 kWh** (nie 12 — §D) | luka szczytu ~7 kWh; przy 8–12 kWh luka ~2 → pomiń vs cykl |
| ForceCharge 13–15 | opcjonalnie / gdy SoC &lt; target | priorytet: **nie oddawać wszystkiego do sieci** |
| Target SoC | **80%** | wystarczy przy silnym PV |

### B. Zima (XI – II)

| Parametr | Propozycja | Uzasadnienie |
|----------|------------|--------------|
| ForceCharge **22–6** | **nie zawsze do 100%** — wg tabeli T×PV (§C): mróz zawsze pełnić; przy T ≥ 5°C i PV ≥ 12 kWh jak lato | pusta noc XI–I bez FC; przy T ≥ 5°C dach często pokrywa szczyt (luka ~0) |
| ForceCharge **13–15** | **włącz**, dopóki SoC &lt; target | po FC nadal dno wieczorem |
| Target SoC | **90–100%** (XI–I), **80–90%** (II) | XII bez FC max ~24% |
| Rezerwa / minSoc | **40%** (już `BATTERY_SOC_RESERVE_WINTER`) | autonomia nocna — **ładuj do niej tylko w taniej G12w**; w szczycie 6–13 / 15–22 **nie** dobijaj z drogiego |
| Min SoC wieczór | **50%** + alert | XI SoC@16~38% = gwarantowana pusta noc |
| „Poczekaj na PV rano” | tylko gdy prognoza **≥ 5–8 kWh** do południa **i** SoC ≥ ~40% | próg 3 kWh latem jest za agresywny zimą |

**Świadomie:** po włączeniu FC **całkowity** import z sieci może wzrosnąć — to OK, jeśli zastępuje drogi import 6–13 / 15–22 tanim 22–6.

### C. Zima — T × droga taryfa × PV (fakt, ~120 dni roboczych X.2025–III.2026)

Źródło: `foxess_report_daily` (`loads`, `PVEnergyTotal`, `gridConsumption`) + `weather_data.temperature_celsius`. G12w droga: pn–pt **6–13** i **15–22**. Weekend / święta = cała tania (poza tabelą).

Zużycie w drogiej **silnie zależy od temperatury** (corr Tśr. dnia vs load_exp **−0,87**): ok. **−1 kWh/°C** w oknach szczytowych. Tśr. działa lepiej niż Tmin (corr −0,73) — grzanie idzie też w dzień.

| T śr. dnia | n | Load droga 6–13 | Load droga 15–22 | **Suma droga** | PV doby | PV w drogich godz. | Luka (load−PV droga) | Import sieci w drogiej (fakt) | Load tania 22–6+13–15 |
|------------|--:|----------------:|-----------------:|---------------:|--------:|-------------------:|---------------------:|------------------------------:|----------------------:|
| **< −5°C** | 13 | 12,8 | 12,1 | **24,9** | 9,8 | 6,8 | **18,1** | 7,6 | **17,6** |
| **−5–0°C** | 23 | 10,7 | 10,0 | **20,6** | 5,7 | 4,2 | **16,5** | 10,4 | 14,3 |
| **0–5°C** | 36 | 8,8 | 6,7 | **15,6** | 10 | 7,3 | **8,3** | 8,1 | 10,5 |
| **5–10°C** | 41 | 6,1 | 4,3 | **10,4** | 15 | 10,8 | **~0** | 2,9 | 6,1 |
| **≥ 10°C** | 8 | 6,4 | 4,3 | **10,7** | 12 | 8,6 | 2 | 3,6 | 4,5 |

Szacunek na wieczór (T śr. **jutro**, kWh w drogiej):

`load_exp ≈ 18 − 1,0 × Tśr`  →  −10°C ≈ **28 kWh** · 0°C ≈ **18** · +5°C ≈ **13** · +10°C ≈ **8**

PV w drogich godzinach zimą ≈ **70%** dobowej produkcji (dach świeci głównie 8–16, czyli w 6–13 + kawałku 15–22).

**Bateria ~10,36 kWh, rezerwa 40% → użyteczne na szczyt ~6,2 kWh** (40%→100%). To **za mało** na lukę przy T ≤ 0°C (16–18 kWh). Nawet pełna bateria + dach nie pokrywa mrozu; tani import nocny jest konieczny, drogi import i tak wraca (fakt: 8–10 kWh sieci w szczycie przy T ≤ 0°C).

Wniosek na **FC 22–6 (advise-only)**, wieczór dnia D, horyzont dzień D+1:

| Tśr jutro | PV jutro (prognoza) | Load droga (szacunek) | Luka po dachu | Nocne ładowanie |
|-----------|---------------------|----------------------:|--------------:|-----------------|
| **< 0°C** | dowolne | ≥ 18 kWh | 16–18 kWh ≫ 6 kWh | **zawsze do 90–100%** — bateria i tak za mała |
| **0–5°C** | **< 12 kWh** | ~16 kWh | ~8 kWh | **do 90–100%** |
| **0–5°C** | **≥ 12 kWh** | ~16 kWh | dach pokrywa większość szczytu | **nie pełnić**; trzymaj rezerwę 40%, ewentualnie 13–15 |
| **≥ 5°C** | **< 8 kWh** | ~10 kWh | dach słaby | **do ~80%** |
| **≥ 5°C** | **≥ 12 kWh** | ~10 kWh | luka ~0 | **jak lato**: FC tylko gdy SoC &lt; 40% |

Dodatkowo: przy mrozie **tania noc sama zjada 14–18 kWh** (grzanie). Magazyn 10 kWh nie buforuje nocy — ForceCharge = **zasilanie domu tanim prądem + napełnienie na rano 6–13**, nie „magazyn na całą dobę”.

Na **B2 zimą** próg nie może być sam `PV < 18 kWh`. Wejście: **Tśr jutro + PV jutro → cel SoC + minuty FC** (30 min ≈ +50 pp SoC). Drobny brak (**&lt; 2 kWh** albo **&lt; 15 pp**) pomijamy — spread G12w (~0,36 zł/kWh) nie pokrywa zużycia cyklu LFP.

### D. Jesień — T × droga taryfa × PV (fakt, 35 dni roboczych 15.09–31.10.2025)

Ta sama metodyka co §C. **Inny driver niż zimą:** corr(Tśr, load_exp) tylko **−0,28** (zima −0,8). Zużycie w drogiej jest **płaskie ~7–11 kWh**, słabo zależy od T (pas 5–15°C). Decyduje **dach**.

| T śr. dnia | n | Load droga | PV doby | PV w drogiej | Luka (load−PV droga) | Import sieć droga |
|------------|--:|-----------:|--------:|-------------:|---------------------:|------------------:|
| **0–5°C** | 3 | 10,5 | 20,0 | 14,0 | **−3,6** | 2,6 |
| **5–10°C** | 15 | 9,1 | 11,1 | 7,8 | **+1,3** | 2,4 |
| **10–15°C** | 13 | 9,7 | 11,3 | 7,8 | **+2,0** | 3,6 |
| **15–20°C** | 4 | 7,1 | 22,1 | 15,4 | **−8,3** | 0,5 |

Szacunek liniowy słaby: `load_exp ≈ 12 − 0,25 × Tśr` — **nie używać jak zimą**. Lepiej patrzeć na **PV jutro**:

| PV doby | n | Load droga | PV w drogiej | **Luka** | Dni z luką &gt; 5 kWh |
|---------|--:|-----------:|-------------:|---------:|---------------------:|
| **&lt; 8 kWh** | 12 | 9,6 | 2,9 | **+6,7** | **50%** |
| **8–12 kWh** | 10 | 9,2 | 6,9 | **+2,2** | 10% |
| **12–18 kWh** | 2 | 11,2 | 12,1 | **~0** | 0% |
| **≥ 18 kWh** | 11 | 8,5 | 17,5 | **−9** | 0% |

PV doby p25/p50/p75: **6 / 10 / 20 kWh**. Aż **63%** dni ma PV &lt; 12, ale przy PV 8–12 luka zwykle mała.

**Wniosek na FC 22–6 jesienią (advise-only):**

| PV jutro | Luka szczytu | Nocne ładowanie |
|----------|-------------:|-----------------|
| **&lt; 8 kWh** | ~7 kWh | **tak** — cel ~80–90% (ΔSoC → minuty; 30 min ≈ +50 pp); włącz/wyłącz okno |
| **8–12 kWh** | ~2 kWh | **pomiń** albo krótko gdy SoC &lt; rezerwy 22% (drobny brak vs cykl) |
| **≥ 12 kWh** | ≤ 0 | **nie** — dach pokrywa szczyt |

Stary próg „jesień: PV &lt; 12” był **za agresywny** (ładowałby też dni z luką ~2 kWh). Docelowo B2 jesień: **PV &lt; ~8 kWh** (ew. 8–12 tylko przy SoC &lt; rezerwy). T nie jest pierwszym filtrem jesienią.

### E. Wiosna — wstępne założenia (fakt: III.2026 n=20 roboczych; V.2025 n=10 — dane niepełne / nietypowe PV)

| Miesiąc | n | Tśr | Load droga | PV doby | Luka | Uwaga |
|---------|--:|----:|-----------:|--------:|-----:|-------|
| **III** | 20 | 6,7 | 11,4 | **22** | **−5** | dach zwykle wygrywa; gap&gt;5 tylko 2 dni |
| **V** | 10 | 12 | ~1 | ~5 | ~−3 | próbka podejrzana (start / luki) — **nie kalibrować** |

W marcu corr(T, load_exp) umiarkowany (~−0,4); PV p50 ~25 kWh. **Wiosna ≈ odwrotność jesieni pod względem PV:** przy typowym dachu FC nocny rzadko potrzebny; reguła bliższa **latu** (FC gdy SoC niski **i** PV jutro bardzo słabe). Pełna kalibracja wiosny **po sezonie III–V.2026** (jak §D).

**Założenie robocze wiosna (do weryfikacji):**
- rezerwa **20%** (jak lato / dolna jesień),
- FC 22–6 tylko gdy **PV jutro &lt; ~8 kWh** i SoC &lt; ~40%,
- od **XI** wraca tabela zimowa §C (T×PV).

---


## Harmonogram wdrożenia (po obronie / równolegle do MVP)

| Faza | Co | Gdzie | Status |
|------|-----|-------|--------|
| **B0** | Zostawić doradcę advise-only (bez auto `foxess_control` na obronę) | API §9.6 | `[x]` MVP |
| **B1** | Sezon **autumn** + **spring** + progi §D–E | `.env` / `battery_advisor.py` / settings | `[x]` 2026-08-27 — jesień PV&lt;8; wiosna III–V jak lato (SoC&lt;40, PV&lt;8); zima XI–II |
| **B2** | FC nocny: **jesień** `PV jutro < ~8 kWh` (§D); **zima** Tśr jutro + PV → kWh w 22–6 (§C) | advisor + prognoza RF 16 + T NWP | `[x]` 2026-08-27 (advise-only; 30 min ≈ 50%; pomiń drobny brak vs cykl) |
| **B3** | Alert / sugestia: „SoC@16 &lt; 50% → nie rozładowuj poniżej rezerwy / włącz 13–15” | mobile Home + notifications | `[x]` BAT.3 (2026-08-27, advise-only) |
| **B4** | Shadow counterfactual: koszt z polityką A/B vs fakt IX–II | `bill_simulator` / savings | `[x]` 2026-08-27 — skrypt + notatka; B≈0 zł, B2≈86 zł, C≈327 zł |
| **B5** | Opcjonalnie: dry-run planu sterowania → log; auto-apply dopiero po B4 | `battery_control` | `[ ]` park |

---

## Co już jest w kodzie (nie wymyślać od zera)

- Zima = **XI–II**, wiosna = **III–V**, jesień = **15.09–31.10**, lato = reszta
- Rezerwa: winter **40%** / autumn **22%** / spring+summer **20%**; min wieczór jesień **45%**
- **Jesień FC:** PV jutro **&lt; ~8 kWh** → cel ~85% (§D); **nie** próg 12
- **Wiosna FC:** jak lato, SoC **&lt; 40%** i PV **&lt; ~8 kWh** (§E)
- Lato: FC nocy tylko poniżej 20%; cap **15 min / +25 pp**; **30 min ≈ +50 pp**
- **B2 zima:** Tśr + PV → cel SoC + minuty; pomiń gdy &lt; 2 kWh / &lt; 15 pp (cykl)
- **Zima 13–15:** SoC &lt; **40%** i Tśr ≤ **5°C** i PV dziś &lt; **~10 kWh** (kalibracja XI–II.2025/26)
- Plan sterowania — **bez** auto-apply w MVP

Luki: brak twardej blokady „nie zjeżdżaj poniżej X% przed 22:00”. UI suwaków sezonu (T4.3) — **zrobione** `/tabs/battery` 2026-08-27; plan dnia SE **uniwersalny**: add/usuń bloki (max 8) + opcjonalne szablony **G11 / G12w / G13** — 2026-08-27. Pełna kalibracja wiosny po III–V.2026.

**Odróżnienie produktu:** plan dnia wynika z taryfy **G12w (Tauron)**, tabel T×PV z *naszych* danych IX–II oraz prognozy RF — advise-only + shadow savings. Wspólne pojęcia branżowe (okna czasu, doładowanie z sieci) nie oznaczają kopiowania ekranu / schedulera producenta falownika.

---

## Jak czytać wykresy (dla obrony)

- **11.09** — bateria niepusta, mały import: typowa wczesna jesień.
- **Pusta bateria rano** (np. 12.09, wiele dni X–XII) = zużycie nocne + brak rezerwy/FC, **nie** „model PV”.
- **Ekran z importem 8 kWh** przy wysokiej produkcji dnia = rozjazd **czasowy** (noc vs dzień), nie bilans dzienny PV.

---

## TODO (checklist)

| ID | Status | Zadanie |
|----|--------|---------|
| BAT.1 | `[x]` | Sezon autumn (15.09–31.10, PV&lt;8) + spring III–V + zima XI–II — wg §D–E 2026-08-27 |
| BAT.2 | `[x]` | FC warunkowy: jesień od PV jutro; zima od Tśr + PV (§C) — w advisorze 2026-08-27 |
| BAT.3 | `[x]` | Alert SoC@16 + sugestia 13–15 / hold reserve — `GET /battery/suggestion` + feed `soc_reserve` + karta Home |
| BAT.4 | `[x]` | Backtest kosztów IX–II (polityka vs fakt) — `scripts/analysis/backtest_battery_policy_ix_ii.py` + [`NOTATKA_BAT4_BACKTEST_IX_II_2026-08-27.md`](NOTATKA_BAT4_BACKTEST_IX_II_2026-08-27.md) |
| BAT.5 | `[x]` | UI `soc_min` = rezerwa sezonowa — auto: lato **20%** / zima 40%; KPI SoC na Home |
| BAT.6 | `[ ]` | Po BAT.4: decyzja o auto-apply (park do świadomej zgody) |

---

*Plan z analizy IX.2025–II.2026 — 2026-08-02; T×droga taryfa×PV zima — 2026-08-27; jesień/wiosna §D–E — 2026-08-27.*
