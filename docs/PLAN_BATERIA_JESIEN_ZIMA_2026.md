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

### A. Jesień (ok. 15.09 – 31.10)

| Parametr | Propozycja | Uzasadnienie |
|----------|------------|--------------|
| Tryb sezonu | **jesień** (dziś kod: lato do IX, zima od X) | IX już 37% pustych nocy |
| Rezerwa SoC | **20–25%** | między lato 15% a zima 40% |
| Min SoC wieczór (alert 16:00) | **40–50%** | X: SoC@16~60 → SoC@22~40 → dużo crashy |
| ForceCharge 22–6 | **warunkowo**: gdy prognoza PV jutro **&lt; ~12 kWh** | X śr. PV 12,7 |
| ForceCharge 13–15 | opcjonalnie / gdy SoC &lt; target | priorytet: **nie oddawać wszystkiego do sieci** |
| Target SoC | **80%** | wystarczy przy silnym PV |

### B. Zima (XI – II)

| Parametr | Propozycja | Uzasadnienie |
|----------|------------|--------------|
| ForceCharge **22–6** | **zawsze** (dni robocze; weekend przy dużym load) | przed FC: 87–100% nocy pustych |
| ForceCharge **13–15** | **włącz**, dopóki SoC &lt; target | po FC nadal dno wieczorem |
| Target SoC | **90–100%** (XI–I), **80–90%** (II) | XII bez FC max ~24% |
| Rezerwa / minSoc | **40%** (już `BATTERY_SOC_RESERVE_WINTER`) | autonomia nocna |
| Min SoC wieczór | **50%** + alert | XI SoC@16~38% = gwarantowana pusta noc |
| „Poczekaj na PV rano” | tylko gdy prognoza **≥ 5–8 kWh** do południa **i** SoC ≥ ~40% | próg 3 kWh latem jest za agresywny zimą |

**Świadomie:** po włączeniu FC **całkowity** import z sieci może wzrosnąć — to OK, jeśli zastępuje drogi import 6–12 tanim 22–6.

---

## Harmonogram wdrożenia (po obronie / równolegle do MVP)

| Faza | Co | Gdzie | Status |
|------|-----|-------|--------|
| **B0** | Zostawić doradcę advise-only (bez auto `foxess_control` na obronę) | API §9.6 | `[x]` MVP |
| **B1** | Dodać sezon **autumn** + progi z tabeli A/B w `.env` / `battery_strategy_settings` | `battery_advisor.py` | `[ ]` |
| **B2** | Reguła: FC nocny jeśli `forecast_pv_tomorrow < threshold` (jesień) | advisor + prognoza RF 16 | `[ ]` |
| **B3** | Alert / sugestia: „SoC@16 &lt; 50% → nie rozładowuj poniżej rezerwy / włącz 13–15” | mobile Home + notifications | `[ ]` |
| **B4** | Shadow counterfactual: koszt z polityką A/B vs fakt IX–II | `bill_simulator` / savings | `[ ]` |
| **B5** | Opcjonalnie: dry-run planu sterowania → log; auto-apply dopiero po B4 | `battery_control` | `[ ]` park |

---

## Co już jest w kodzie (nie wymyślać od zera)

- Zima = **X–III**, target 80%, min evening 50%, reserve winter **40%** / summer 15%
- Okna G12w FC: **22–6**, **13–15**
- Plan sterowania (ForceCharge / minSoc / SelfUse) — **bez** auto-apply w MVP

Luki: brak pasa **jesień**; UI `soc_min=20` ≠ rezerwa zima 40%; brak powiązania **prognozy PV jutro → FC**; brak twardej blokady „nie zjeżdżaj poniżej X% przed 22:00”.

---

## Jak czytać wykresy (dla obrony)

- **11.09** — bateria niepusta, mały import: typowa wczesna jesień.
- **Pusta bateria rano** (np. 12.09, wiele dni X–XII) = zużycie nocne + brak rezerwy/FC, **nie** „model PV”.
- **Ekran z importem 8 kWh** przy wysokiej produkcji dnia = rozjazd **czasowy** (noc vs dzień), nie bilans dzienny PV.

---

## TODO (checklist)

| ID | Status | Zadanie |
|----|--------|---------|
| BAT.1 | `[ ]` | Sezon `autumn` + parametry w env/DB |
| BAT.2 | `[ ]` | FC warunkowy od prognozy PV (jesień) |
| BAT.3 | `[ ]` | Alert SoC@16 + sugestia 13–15 / hold reserve |
| BAT.4 | `[ ]` | Backtest kosztów IX–II (polityka vs fakt) |
| BAT.5 | `[ ]` | Zsynchronizować UI `soc_min` z rezerwą sezonową |
| BAT.6 | `[ ]` | Po BAT.4: decyzja o auto-apply (park do świadomej zgody) |

---

*Plan z analizy IX.2025–II.2026 — 2026-08-02.*
