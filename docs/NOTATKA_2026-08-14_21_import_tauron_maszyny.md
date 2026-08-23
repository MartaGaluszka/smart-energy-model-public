# Notatka — import Tauron / maszyny budowlane (14–21.08.2026)

**Okres:** 14.08–21.08.2026  
**Źródło:** obserwacja użytkownika  
**DB:** `household_events` id=**2** (event_date=2026-08-14, type=`maszyny_budowlane`, impact=`up`) · `weather_notes` `#146`

---

## Treść

W okresie **14–21.08** zwiększony **import z Tauron** na poziomie ok. **1,2–1,5** — związane z **używaniem maszyn budowlanych**.

## Kontekst MLOps / bilans

- To wyjaśnienie **podwyższonego importu sieci**, nie błędu modelu PV ani closeoutów produkcji.
- Przy analizie bilansu domu / ROI / rekomendacji zużycia w tym oknie: uwzględnić obciążenie budowlane.
- Closeouty PV (FoxESS generation) pozostają osobno — maszyny wpływają na **import**, nie na `actual_kwh` produkcji paneli.

Powiązane closeouty w oknie: 14–21.08 (m.in. 17 CS4, 18 zawyżenie, 19 zaniżenie, 20 peak_cs4, 21 peak).
