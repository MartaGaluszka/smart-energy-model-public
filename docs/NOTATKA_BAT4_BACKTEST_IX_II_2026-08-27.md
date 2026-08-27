# BAT.4 — backtest kosztów baterii IX–II (2026-08-27)

**Okno:** 2025-09-01 → 2026-02-28 · **Skrypt:** `scripts/analysis/backtest_battery_policy_ix_ii.py`  
**Advise-only** — walidacja, nie reguła live / nie auto-apply.

## Wynik (próbki FoxESS 5-min, stawki G12w z `tauron_tariff`)

| Polityka | Opis | Oszczędność vs fakt | Koszt |
|----------|------|---------------------|-------|
| **A** | Fakt (import × strefa) | — | **~2526 zł** |
| **B** | Przesuń drogie FC baterii → tania G12w | **~1 zł** (4,6 kWh) | ~2525 zł |
| **B2** | Trzymaj rezerwę sezonową w szczycie (doradca) | **~86 zł** (≈242 kWh) | ~2440 zł |
| **C** | Sufit: cały import z1 jak z2 | ~327 zł | ~2199 zł |

Import: ~983 kWh z1 + ~3036 kWh z2.

## Werdykt

1. **Timing FC jest już dobry** — prawie nie ładujecie baterii z sieci w drożej strefie (B ≈ 0).
2. **Wartość doradcy = rezerwa / nocny FC pod szczyt** (B2 ≈ **86 zł** w sezonie IX–II) — spójne z BAT.3 i B2, nie z „przesuwaniem FC”.
3. **C (~327 zł)** to nierealny sufit taryfowy (całe zużycie szczytowe w taniej).
4. **BAT.6 / auto-apply** — nadal park; backtest nie odblokowuje sterowania.

## Jak powtórzyć

```bash
PYTHONPATH=. python scripts/analysis/backtest_battery_policy_ix_ii.py
```

*Przybliżenie B2: nie pełny replay SoC godzina×godzina; deficyt do rezerwy × spread z1−z2.*
