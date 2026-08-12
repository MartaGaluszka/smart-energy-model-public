# README rewrite — task list (local)

**Status:** domknięte — README PL + hub + screenshoty + GIF tour  
**Screenshoty:** [`docs/images/app/`](images/app/) (`s1`–`s4` + `app-tour.gif`)

**Owner:** Marta Gałuszka  
**Goal:** Short portfolio README: purpose → value → data flow → FoxESS limits → app HOW TO.

---

## Target README outline

| # | Section | Status |
|---|---------|--------|
| 1 | Purpose (portfolio, non-commercial) | ✅ w [`README.md`](../README.md) |
| 2 | Value model + app | ✅ |
| 3 | FoxESS → processing (SQLite / Postgres) | ✅ |
| 4 | Model → app → value | ✅ |
| 5 | Possess data + API limits | ✅ |
| 6 | Quick HOW TO (+ screenshot paths) | ✅ tekst · ✅ PNG + GIF |

---

## Tasks

### T0 — Prep

- [x] **T0.1** Inventory: stary metric-dump usunięty z głównego README.
- [x] **T0.2** Source of truth liczb = [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md); README tylko snapshot.
- [x] **T0.3** Stack: host MLOps = SQLite + `mlops/` + launchd · app = Docker Postgres + API + Ionic — opisane w README §3.
- [x] **T0.4** Screenshoty S1–S4 + animacja [`app-tour.gif`](images/app/app-tour.gif) w [`docs/images/app/`](images/app/) — z iOS Simulator (2026-08-05); 3 s / slajd, crossfade.

### T1–T5 — Treść README

- [x] **T1** Purpose / disclaimer / sukces pipeline+app  
- [x] **T2** User story, model PVE, wartość app, diagram ASCII  
- [x] **T3** Sync path, dual storage, kroki przetwarzania, linki  
- [x] **T4** Artefakty API, UI, raw vs hybryda, value statement  
- [x] **T5** `.env`, paczki miesięczne, 40402, incremental vs backfill, Postgres compose + migrate  

### T6 — HOW TO

- [x] **T6.1** Prerequisites  
- [x] **T6.2** docker compose + `npm start`  
- [x] **T6.3** [`images/app/`](images/app/): `s1-sync.png` … `s4-sugestie.png` + `app-tour.gif` · wpisane w README §6  
- [x] **T6.4** Troubleshooting  

### T7 — Cleanup

- [x] **T7.1** Główny [`README.md`](../README.md) PL  
- [x] **T7.2a** Hub [`STATUS_ML_MLOPS.md`](STATUS_ML_MLOPS.md)  
- [x] **T7.2b** Snapshot README → hub  
- [x] **T7.2c** Kanony 01/02/03/mlops/CHANGELOG — bez nowych równoległych dumpów  
- [x] **T7.2d** [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) → przekierowanie do huba  
- [x] **T7.2e** [`mlops/README.md`](../mlops/README.md) — 04:30, dual shadows, rozróżnienie API Docker  
- [x] **T7.3** Dla oceniającego: 5 linków (prezentacja · 03 · STATUS · FoxESS · HOW TO)  
- [x] **T7.4** Język README = **PL**  
- [x] **T7.5** Smoke-read: outsider dostaje cel → Fox → app bez notebooków; metryki w hubie  

---

## Where numbers / ops live (ustalone)

| Temat | Home |
|-------|------|
| Data quality | `docs/01_EDA_analiza.md` |
| Model method + offline | `docs/02_ML_predykcja_PV.md` |
| Decisions | `docs/03_ZALOZENIA_I_DECYZJE.md` |
| MLOps schedule | `mlops/README.md` |
| Gate history | `docs/CHANGELOG_ML.md` |
| **Current snapshot** | `docs/STATUS_ML_MLOPS.md` |

---

## Definition of done

1. [x] README sekcje 1→6  
2. [x] Portfolio / non-commercial  
3. [x] Fox → process → app  
4. [x] API limits actionable  
5. [x] HOW TO + screenshoty PNG + GIF tour  
6. [x] STATUS hub + brak potrójnych metryk  
7. [x] Checklist  

---

## Screenshoty / animacja (T0.4 · T6.3)

11 slajdów · **3 s** hold · crossfade ~0,5 s

![Tour aplikacji Smart Energy](images/app/app-tour.gif)

| Artefakt | Uwagi |
|----------|--------|
| Tour GIF | 11 slajdów · ~8,5 MB · pełna rozdzielczość |
| S1 `s1-sync.png` | Home + status sync Fox |
| S2 `s2-prognoza-dzis.png` | Prognoza dziś (profil) |
| S3 `s3-prognoza-jutro.png` | Closeout 04.08 (inny dzień) |
| S4 `s4-sugestie.png` | Symulator — wynik / oszczędność |

![Home](images/app/s1-sync.png)
![Prognoza](images/app/s2-prognoza-dzis.png)
![Closeout 04.08](images/app/s3-prognoza-jutro.png)
![Symulator](images/app/s4-sugestie.png)

---

*Updated 2026-08-05 · path: `docs/README_REWRITE_TASKS.md`*
