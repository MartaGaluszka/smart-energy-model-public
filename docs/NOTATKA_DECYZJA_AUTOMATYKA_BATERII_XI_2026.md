# Decyzja — automatyka baterii od listopada 2026 (skrócony gate)

**Data:** 2026-10-31  
**Status:** w toku · **porcja 1** (sugestie wieczorne) · **porcja 3+** (apply Fox)  
**Powiązane:** [`ZADANIA_IMPLEMENTACJA_MOBILNA.md`](ZADANIA_IMPLEMENTACJA_MOBILNA.md) §Sprint XI · [`NOTATKA_REGULA_BATERIA_POCHMURNO_22.md`](NOTATKA_REGULA_BATERIA_POCHMURNO_22.md) · [`NOTATKA_BATERIA_SOC_LOG.md`](NOTATKA_BATERIA_SOC_LOG.md)

---

## Werdykt (1 zdanie)

> Od **XI 2026** włączamy **automatykę na produkcji** (Mac + launchd + reguła B2), z **guardrails** i walidacją **na żywo** (log, min SoC rano, Tauron Z1/Z2) — zamiast czekać ~12 mies. wyłącznie w trybie shadow-only; październik 2025/2026 pokazał, że **człowiek też myli się**, a **w nocy nie ma operatora**.

---

## Dlaczego skrócony gate (vs §9.6 „~1 rok”)

| Argument | Źródło |
|----------|--------|
| Noc **22–6** — brak obecności przy FC / stopie | log SoC · case **15→16**, **13→14** |
| Reguła B2 + kalendarz **już w kodzie** | `evaluate_charge_tonight_cloudy` od 2026-08-27 |
| Październik **2026:** shift importu **~81% strefa 2** vs **~51%** w X 2025 | Fox + Tauron (analiza 2026-10-31) |
| Błędy człowieka **porównywalne** z modelem PV | paper + FC log |

---

## Guardrails (obowiązkowe)

1. **Tylko G12w strefa 2** — apply FC **22–6** i **13–15** (pn–pt); **zakaz** celowego ładowania baterii ze **szczytu** (strefa 1).
2. **Timer stop FC** — koniec po **N minutach** z reguły B2 (Fox sam nie ucina — lekcja **13→14**).
3. **Kill-switch:** `BATTERY_CONTROL_ENABLED=0` w `.env` → natychmiast dry-run / brak apply.
4. **Audit:** `data/processed/battery_control_log.csv` + (później) API audit.
5. **Cap:** `BATTERY_CONTROL_MAX_APPLIES_PER_DAY`, `BATTERY_CONTROL_EVENING_ONLY=1` (porcja 3).
6. **Opt-in użytkownika** w apce (T6.1) przed traktowaniem automatyki jako domyślnej.

---

## KPI listopada (sukces / rollback)

| KPI | Cel | Rollback gdy |
|-----|-----|--------------|
| **min SoC 5–8** (dni robocze) | ≥ **25%** mediana; brak śniadania z sieci w szczycie | >3 dni z rzędu **&lt;15%** + import Z1 rano |
| **Zbędne kWh tanio** (FC przy jutrze RF/ENS ≥12) | spadek vs październik ręczny | mediana **&gt;4 kWh/noc** przez tydzień |
| **Import Z2 / total** | utrzymać **≥75%** w strefie 2 | spadek **&lt;60%** |
| **Log vs intuicja** | ≥ **55%** zgodności z „co bym zrobiła” (dry-run tydz. 1) | chaos w logu / API Fox błędy |

Rollback: **`BATTERY_CONTROL_ENABLED=0`**, powrót do advise-only + ręczne FC.

---

## Fazy wdrożenia (Sprint XI)

| Porcja | Zakres | Stan |
|--------|--------|------|
| **1** | Notatka + `evening` sugestie (`charge_tonight_cloudy`) | **2026-10-31** |
| **2** | `battery_control` context `evening` + testy | **2026-10-31** |
| **3** | launchd 21:15 / 22:00 / 22+N + `--apply` | plan |
| **4** | Toggle apka + API | plan |

---

## Publiczne repo

W klonie publicznym: **bez** ścieżek `/Users/…`, SN, `.env`; ta notatka może być **skrócona** (bez paper-trade) — link do `ZADANIA` publicznego bez sekcji prywatnych logów.
