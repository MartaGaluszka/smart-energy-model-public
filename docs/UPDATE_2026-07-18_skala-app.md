# Aktualizacja produkcyjna — 2026-07-18 (A) — skala app

**Zakres:** próba skalowania profilu ∫`pvPower` do dziennego `PVEnergyTotal` — **WYCOFANA** (~16:26)

Powiązane: [UPDATE_2026-07-18_target-pve.md](UPDATE_2026-07-18_target-pve.md) · [CHANGELOG_ML.md](CHANGELOG_ML.md) · [NOTATKA_RETRENINGI_LIPIEC_2026.md](NOTATKA_RETRENINGI_LIPIEC_2026.md) · [UPDATE_2026-07-17_gps-icon.md](UPDATE_2026-07-17_gps-icon.md)

---

## 1. Problem, który chcieliśmy rozwiązać

| Warstwa | Skala |
|---------|--------|
| Trening / RF (do 18.07 rano) | ∫`pvPower` (~**wyżej**) |
| Closeout / app FoxESS | `PVEnergyTotal` (~**niżej**) |

Skutek: systematyczne „zawyżenie” operacyjne ~**10–15%** — model i aplikacja mówiły o innych liczbach.

---

## 2. Co próbowano (~16:26)

**Pomysł:** zostawić trening na `pvPower`, a **profil godzinowy** przeskalować do dziennego PVE z app (skala dnia).

| Element | Wartość |
|---------|---------|
| Backup przed próbą | `pv_hourly_model_before_app_scale.joblib` (= stan GPS+ICON, target ∫pvPower) |
| Status | **wycofane tego samego dnia** (~kilka minut później) |

---

## 3. Dlaczego wycofane

- Skalowanie profilu **nie** rozwiązuje źródła: trening i closeout nadal na **innych** zmiennych.
- Ryzyko maskowania błędu zamiast naprawy targetu.
- Decyzja: przejść od razu na **bezpośredni target ΔPVEnergyTotal** — patrz [UPDATE_2026-07-18_target-pve.md](UPDATE_2026-07-18_target-pve.md).

---

## 4. Co zostało z tej próby

| Artefakt | Rola teraz |
|----------|------------|
| `pv_hourly_model_before_app_scale.joblib` | Rollback do ICON + ∫pvPower (sprzed PVE) |
| Ten dokument | Ślad w historii wdrożeń — żeby nie powtarzać skali app |

---

## 5. Rollback do stanu sprzed obu zmian 18.07

```bash
cp models/pv_hourly_model_before_app_scale.joblib models/pv_hourly_model.joblib
# w .env:
# PV_HOURLY_TARGET=pvpower
# OPENMETEO_MODEL=icon_seamless
```

---

*Aktualizacja A z 18.07 — wycofana; produkcja = UPDATE B (PVE).*
