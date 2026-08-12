# Train/Test Split — incydent wiosenny (archiwum)

> **Status dokumentu:** 📦 **ARCHIWUM** — opis problemu i propozycji z **9 lipca 2026**.  
> **Nie opisuje obecnej metody produkcyjnej.**

**Obecna strategia ML (lipiec 2026):** losowy podział **80/20 po dniach** na zbiorze 2025-06-01 → 2026-05-31 (`random_state=42`). Test zawiera dni ze **wszystkich sezonów** — problem „test = 88% wiosna” został rozwiązany inną ścieżką niż przesunięcie dat holdoutu.

**Gdzie szukać aktualnych ustaleń:**
- [docs/02_ML_predykcja_PV.md](../../02_ML_predykcja_PV.md) §1.2 — split 80/20
- [docs/03_ZALOZENIA_I_DECYZJE.md](../../03_ZALOZENIA_I_DECYZJE.md) §1, §4
- [notebooks/02_ML_predykcja_PV.ipynb](../../../notebooks/02_ML_predykcja_PV.ipynb)

**Production Holdout** (dev → 2026-05, test 2026-06+) — osobna, **historyczna** strategia do porównania RF vs XGBoost; opisana w [docs/02_ML_predykcja_PV.md §3](../../02_ML_predykcja_PV.md) jako archiwum.

---

## Co tu było opisane (kontekst historyczny)

**Data analizy:** 9 lipca 2026  
**Problem:** Przy **holdoucie czasowym** train nie miał wiosny, a test składał się w ~88% z wiosny.

---

## Obecny wtedy (ZŁY) Split

**Train:** 2025-06 → 2026-01 (219 dni)
- Lato: 92 dni
- Jesień: 91 dni  
- Zima: 36 dni
- **Wiosna: 0 dni** ❌

**Test:** 2026-02 → 2026-06 (99 dni)
- **Wiosna: 87 dni (88%)** ⚠️
- Zima: 8 dni
- Lato: 4 dni

**Problem:** Model testowany na sezonie, którego nigdy nie widział w treningu.

---

## Propozycje z tamtego dokumentu

**Option 1: Maksymalny Train**
- Train: 2025-06 → 2026-04 (~330 dni)
- Test: 2026-05 → 2026-06 (~60 dni)

**Option 2: Zbalansowany**
- Train: 2025-06 → 2026-03 (~300 dni)
- Test: 2026-04 → 2026-06 (~90 dni)

**Korzyści obu (wtedy zakładane):**
- Train ma wszystkie 4 sezony
- Model widzi wiosnę w treningu
- Lepsza generalizacja sezonowa

---

## Jak to się skończyło w projekcie

| Etap | Decyzja |
|------|---------|
| Lipiec 2026 | Przejście na **losowy 80/20 po dniach** — test sezonowo wymieszany |
| Ablacja cech | Wyrzucenie `month` / `doy_*` — kalendarz redundantny wobec radiacji + cech słonecznych |
| Model produkcyjny | **16 cech**, Test MAE **0.661 kWh/h**, gap **0.103** |
| Operacje | MLOps: sync + prognoza hybrydowa + launchd 5:00/12:00 |

Incydent wiosenny nadal jest **cennym argumentem w pracy** (dlaczego split czasowy był ryzykowny), ale **nie jest już metodą walidacji wdrożonego modelu**.

---

## Oczekiwany efekt (oryginalna notatka z 09.07 — nieaktualna prognoza)

Z `day_length_hours` przy **starym** splitcie autor oczekiwał spadku MAE o ~0.15–0.25 kWh po przesunięciu dat.  
Finalnie ocena modelu opiera się na **80/20 + ablacji** — patrz `data/processed/ablation_results.csv`.

---

*Archiwum · Smart Energy Model · oryginał: 2026-07-09 · uzupełnienie kontekstu: 2026-07-14*
