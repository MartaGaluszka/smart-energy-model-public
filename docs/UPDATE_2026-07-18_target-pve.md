# Aktualizacja produkcyjna — 2026-07-18 (B) — target PVE

**Zakres:** target godzinowy = **ΔPVEnergyTotal** (jak w app FoxESS) · ~16:32

Powiązane: [UPDATE_2026-07-18_skala-app.md](UPDATE_2026-07-18_skala-app.md) · [CHANGELOG_ML.md](CHANGELOG_ML.md) · [NOTATKA_RETRENINGI_LIPIEC_2026.md](NOTATKA_RETRENINGI_LIPIEC_2026.md) · [UPDATE_2026-07-17_gps-icon.md](UPDATE_2026-07-17_gps-icon.md)

---

## 1. Decyzja

Po wycofaniu skali app (UPDATE A): **trenować i oceniać na tej samej zmiennej co aplikacja**.

| Element | Wartość |
|---------|---------|
| `PV_HOURLY_TARGET` | **`pve`** (domyślne; alias `app`) |
| Metoda | godzinowe **dodatnie delty** licznika `PVEnergyTotal` z `foxess_timeseries` |
| Closeout | ta sama suma godzin = dzienne PVE z app |
| Hiperparametry | `max_depth=6`, `min_samples_leaf=20`, `min_samples_split=20` |

**Sanity 18.07:** Σ ΔPVE godzin = **22.20** = report/app (∫pvPower było **25.11**).

---

## 2. Gate offline

Oba modele oceniane na targetcie PVE; baseline = stary model (∫pvPower) na danych PVE.

| Metryka | Baseline (stary) | Kandydat (PVE) | Δ |
|---------|------------------|----------------|---|
| Test MAE [kWh/h] | 0.568 | 0.582 | +0.014 |
| Gap | 0.009 | 0.040 | +0.031 |
| Daily MAE [kWh/d] | 3.45 | 3.57 | +0.124 |

**Decyzja: ACCEPT (operacyjnie)** — Test MAE w tolerancji REVIEW (+0.014 ≤ 0.02); wdrażamy ze względu na **spójność zmiennej** z app. Obserwacja ≥7 dni closeoutów.

| Artefakt | Rola |
|----------|------|
| `pv_hourly_model.joblib` | **Produkcja — target PVE** |
| `pv_hourly_model_before_pve_direct.joblib` | Backup tuż przed PVE |
| `pv_hourly_model_before_app_scale.joblib` | Backup ICON + ∫pvPower (sprzed obu prób 18.07) |

---

## 3. Fundament po 18.07 (stan „wdrożeniowy 16 cech”)

| # | Zmiana | Kiedy |
|---|--------|-------|
| 1 | GPS dach | 17.07 |
| 2 | ICON | 17.07 |
| 3 | **Target PVE** | **18.07** ← ten dokument |

Model primary nadal **16 cech**; CS4 (19) dopiero dual od 26.07 — [UPDATE_2026-07-26_cs4-dual.md](UPDATE_2026-07-26_cs4-dual.md).

---

## 4. Uwaga operacyjna

| Warstwa | 14–17.07 | Od ~16:32 18.07 |
|---------|----------|------------------|
| Rzeczywistość na wykresie | app / PVE | to samo |
| Snapshoty prognoz w archiwum | GPS/ICON, target **∫pvPower** | kolejne runy: **PVE** |
| Pierwszy pełny closeout 5:00 na PVE | — | od **19.07** (lub ręczny run 18.07 wieczór) |

---

## 5. Rollback

```bash
# Wróć do ICON + ∫pvPower (przed PVE / przed skalą app)
cp models/pv_hourly_model_before_app_scale.joblib models/pv_hourly_model.joblib
# PV_HOURLY_TARGET=pvpower
```

---

*Aktualizacja B z 18.07 — obowiązujący target produkcji do dualu CS4.*
