# Podsumowanie — **CS4 operacyjny** + przygotowanie **L30 twardy gate** (XI 2026)

**Data:** 2026-10-31  
**Od 01.11:** [`NOTATKA_DECYZJA_CS4_XI_2026.md`](NOTATKA_DECYZJA_CS4_XI_2026.md) · go-live [`NOTATKA_GO_LIVE_CS4_2026-11.md`](NOTATKA_GO_LIVE_CS4_2026-11.md)  
**L30 (soft → hard):** [`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) · [`NOTATKA_GATE_DUAL_L30.md`](NOTATKA_GATE_DUAL_L30.md)

---

## 1. Skrót decyzji CS4 (operacja)

| Warstwa | Od 01.11.2026 |
|---------|----------------|
| **Apka + bateria** | Accu **pochmurny/ciemny** (Lumen **1–4**, cloud ≥70%, opad ≥2 mm…) → prognoza **CS4** (`ACCU_CS4_UI=1`) |
| **Ensemble (ENS)** | **Shadow operacyjny** — audit w UI, closeout, **`ENSEMBLE_PRIMARY=1`** w launchd bez zmian |
| **Mix/jasny / brak Accu** | Display = **ensemble** |
| **Retrening** | Niedziela **04:30** — RF16 + **CS4** + XGB (`train_dual_weekly.sh`); L30 liczone dla **wszystkich** feature setów |

**Dlaczego:** listopad 2025 ~**84%** chmur; ENS na pochmornych **~45%** vs CS4 **~35%** |APE| @05 (review); bateria nie może jechać na zawyżonym ENS zimą.

---

## 2. L30 — co to jest i gdzie jesteśmy

### Trzy testy jakości (nie mylić z pickiem w apce)

| # | Test | Rola dziś | Gate |
|---|------|-----------|------|
| 1 | **Shuffle** 80/20 po dniach | kontrola overfitu | **twardy** Δ vs poprzedni weekly |
| 2 | **L30** chrono (ostatnie 30 dni do `train_end`) | uczciwy błąd sezonu | **soft** (INFO/WATCH, `hard_reject=False`) |
| 3 | **Closeout live** @05 vs Fox | tydzień pn–nd, **WAPE/bias** | OK / WATCH / ALARM |

**L30 ≠ prognoza dnia** — to metryka offline po retrainie; **operacyjny CS4 w apce** nie zastępuje L30, tylko dodaje **trzeci tor live** (display CS4 vs Fox w notatkach).

### Historia punktów L30 (`weekly_dual_metrics.csv`)

Stan **2026-10-31** (przed niedzielą **02.11**):

| Model | Punkty L30 (pełne) | Ostatni `recorded_at` | L30 godz. | L30 daily |
|-------|-------------------:|----------------------|----------:|----------:|
| **RF16 production** | **5** | 2026-10-25 | **0,800** | **4,67** |
| **CS4** | **4** | 2026-10-25 | **0,767** | **4,24** |
| **XGB+TS** | **5** | 2026-10-25 | **0,772** | **4,52** |

**Niedziela 02.11 ~04:30** (`train_dual_weekly.sh`) → **6. punkt L30** dla RF16 (warunek gate: ≥ **6** tygodni) — pierwsza **ocena formalna** warunków 1–4 planowana **~08.11** ([`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) § harmonogram).

Ostatni shuffle RF16: **0,673** ACCEPT (Δ **+0,003** vs 18.10). L30 chrono RF16 **0,872** (11.10) spadło do **0,800** (25.10) — typowa zmienność jesieni, nadal **INFO**.

---

## 3. Przejście L30 soft → **twardy gate** (checklist ~08.11)

Wszystkie **4** warunki **naraz** ([`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md)):

| # | Warunek | Stan 31.10 | Do zrobienia XI |
|---|---------|------------|-----------------|
| 1 | **≥6** punktów L30 / model (RF16) | **5** → **6** po weekly **02.11** (CSV) | **nie** w weekly 02.11 — tylko przy review **~08.11** |
| 2 | Próg WATCH = **P90 historii L30** (nie stałe 0,75–1,0) | jesień skalibrowana | po 6. punkcie: przeliczyć P90 RF/CS4/XGB |
| 3 | **Spearman** L30 daily vs WAPE **następnego** tygodnia ≥ **0,5** | za mało par (gate: L30 nie przewidział kolejności live CS4 vs ENS) | zbierać pary od XI; **nie** używać L30 do wyboru CS4 w apce |
| 4 | Rollback **tylko** gdy: L30 > P90 **i** shuffle REVIEW **i** closeout WATCH/ALARM | brak auto-rollback | ręczna decyzja |

**Monitor:** L30 − shuffle > **0,25** kWh/h → sygnał „sąsiednie dni” (RF16 ~0,13 — OK).

**Zima (XII–I):** przeliczyć progi closeout i P90 L30 — krótszy dzień obniża MAE w kWh/h ([`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) § rewizja).

---

## 4. CS4 operacyjny a L30 — jak raportować listopad

| Raport | ENS (shadow MLOps) | CS4 (display gdy pochmurny) |
|--------|-------------------|------------------------------|
| Weekly L30 / shuffle | tak (production joblib) | tak (`feature_set=cs4`) |
| Closeout @05 | tak (`daily` w history) | tak (`daily_cs4`) + **Fox vs suma display** w notatce dnia |
| Paper Accu | tylko prywatne | pick vs Fox |
| Gate primary `.joblib` | **bez auto-zmiany** z L30 soft | CS4 joblib retrenowany co niedzielę |

**Raportowanie rozdzielone (31.10):**

| Notatka | Co wchodzi |
|---------|------------|
| **`NOTATKA_WEEKLY_2026-11-02.md`** (i kolejne do ~08.11) | CS4 live closeout + shuffle/train · **bez sekcji L30** |
| **`NOTATKA_GATE_L30_CLOSEOUT.md`** + dedykowany weekly **~08.11** | L30 historia, P90, Spearman, decyzja twardy gate |

W weekly XI (CS4): WAPE/bias **ENS @05**, **CS4 @05** na dni **Accu pochmurne**, opcjonalnie routing display vs Fox — **nie** mieszać z werdyktem L30 w tej samej notatce.

---

## 5. Harmonogram XI 2026

| Kiedy | Akcja |
|-------|--------|
| **01.11** | Go-live `ACCU_CS4_UI=1` · Accu dzienne · smoke `./mlops/smoke_accu_cs4_routing.sh` |
| **02.11 ~04:30** | `train_dual_weekly.sh` (L30 **w CSV**, nie w treści weekly) · [`NOTATKA_WEEKLY_2026-11-02.md`](NOTATKA_WEEKLY_2026-11-02.md) = **CS4 + shuffle** |
| **~08.11** | Osobna notatka / sekcja: **decyzja** soft→hard L30 (warunki 1–4) — nie mylić z go-live CS4 |
| **co tydzień** | WAPE/bias closeout ([`NOTATKA_GATE_L30_CLOSEOUT.md`](NOTATKA_GATE_L30_CLOSEOUT.md) tabele) |
| **XII–I** | Rewizja progów zimowych |

**Komendy:**

```bash
./mlops/train_dual_weekly.sh
PYTHONPATH=$PWD ./venv/bin/python scripts/train/weekly_dual_gate_report.py
./mlops/smoke_accu_cs4_routing.sh
```

---

## 6. Werdykt roboczy (31.10)

- **CS4 w apce/baterii:** **TAK** od 01.11 — ensemble **shadow** (audit + launchd).
- **L30 twardy gate:** **JESZCZE NIE** — po weekly **02.11** mamy historię na **ocenę ~08.11**; do tego czasu L30 pozostaje **INFO**, shuffle = jedyny twardy gate wag `.joblib`.
- **Nie** przełączać primary MLOps na sam CS4 z powodu L30 daily MAE — L30 **nie** potwierdził kolejności live vs CS4 (gate 07.10); operacyjny CS4 to **Accu + pochmurne**, nie L30.

Powiązane: [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md) · [`NOTATKA_POGODA.md`](NOTATKA_POGODA.md) (wiersz decyzji 31.10)
