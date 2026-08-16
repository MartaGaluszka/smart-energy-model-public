# Notatka pogoda — 16–18.08.2026 (Meteoblue MultiModel)

**Data notatki:** 2026-08-16 ~09:40 (MB meteogram + MultiModel)  
**Lokalizacja:** okolice Krakowa (dokładne GPS tylko w lokalnym `.env`)  
**Produkcja ML:** Open-Meteo **ICON** (`icon_seamless`)  
**UKMO / Accu / MB:** tylko obserwacja ręczna — **nie** w prod

Poprzedni skrót Accu 15.08: poniżej w historii; ten plik = odczyt z **MB 16.08 rano**.

---

## Skrót (konsensus MB)

| Dzień | T max (≈) | Chmury / opady | PV (oczekiwane) |
|-------|----------:|----------------|-----------------|
| **16.08** niedz. | **33–34°C** | prawie 0% cloud do wieczora, 0 mm; wilgotność ↓ ~25% po południu | **bardzo wysoka** |
| **17.08** pon. | **~26°C** | chmury rosną od południa; deszcz/przelotne + burze od ~15:00, nasilenie wieczorem | **umiarkowana → słaba** (okno południe ≠pewne) |
| **18.08** wt. | **~18–20°C** | ~100% cloud, deszcz ciągły (noc→popołudnie), porywy ~40 | **bardzo słaba** |

Ensemble: GFS/ECMWF + hi-res; sumaryczne opady do wtorku wieczorem ~**25–50 mm** (spread hi-res duży).

---

## ICON vs UKMO (MultiModel, wiersze ICON-12 / ICON-7 / UKMO-10)

| Dzień | ICON (12 / 7) | UKMO-10 | Różnica dla PV |
|-------|---------------|---------|----------------|
| **16.08** | Słońce cały dzień; chmury dopiero późny wieczór / noc | Jak ICON; chmury wieczorem **nieco wcześniej** (~19:00) | **Zgodność** — oneshot UKMO bez sensu |
| **17.08** | Rano pochmurno → **okno jaśniejsze ~11–13** → deszcz od ~**15:00** | Bez okna południowego: chmury rano, **deszcz wcześniej (~12–13)** | **UKMO bardziej „mokry / wcześniej”**; ICON daje szansę na generację w południe |
| **18.08** | Deszcz + burze noc/rano; ICON-12 bywa z **przerwą** po południu (~16:00+), ICON-7 dłużej mokry | Deszcz **cały dzień** (ikony deszczu do końca okna) | **UKMO bardziej pesymistyczny**; obie strony = niski PV |

**Werdykt porównania**

- **16.08:** ICON ≈ UKMO (upał, sucho) — prod ICON OK.  
- **17.08:** **główny rozjazd** = timing frontu / okno PV w południe. Closeout i shadow **CS4 vs RF** mają sens właśnie tu (pochmurno + niepewność godzinowa).  
- **18.08:** obie strony „mokre”; różnica w długości deszczu, nie w kierunku dnia.  
- **Nie podmieniać** primary na UKMO — tylko notatka + ewentualny oneshot test w shadow.

---

## Meteogram MB (konsensus, ~09:40)

- **16.08:** 33°C, słońce, 0 mm, porywy wieczorem ~35 km/h.  
- **17.08:** 26°C, burze; low cloud od ~12–15, opady przelotne od ~15, nasilenie do północy.  
- **18.08:** 20°C, ciągły deszcz, gęste chmury cały dzień, porywy ~40.  
- **19–20.08:** powrót (23→27°C), jaśniej — poza oknem closeoutu frontu.

Wiatr / RH (ensemble): 16.08 sucho (RH↓); 17.08 wilgotno 50–90% → ~100% nocą; 18.08 nadal wilgotno, outliery wiatru (jeden model ~40 km/h w południe).

---

## Operacyjnie

| Kiedy | Co robić |
|-------|----------|
| **16.08** | Peak PV; daily już na wagach weekly 04:30 |
| **17.08** | Closeout RF16 vs **CS4** (nowe wagi) + zapis: czy było okno południe (ICON) czy deszcz wcześniej (UKMO) |
| **18.08** | Drugi dzień frontu — niski PV, dobre na „mokry” bias modeli |

Weekly: [`NOTATKA_WEEKLY_2026-08-16.md`](NOTATKA_WEEKLY_2026-08-16.md)

---

## Historia — Accu 15.08 (~11:00), dla porównania run-upu

| Dzień | Accu wtedy | Uwaga vs MB 16.08 |
|-------|------------|-------------------|
| 15.08 | 33°C, cloud 3%, 0 mm | zgodne z weekendem |
| 16.08 | 34°C, cloud 23%, 0 mm | MB dziś jeszcze suchszy (cloud ~0) |
| 17.08 | 20°C, cloud 94%, **14,7 mm**, P=87% | Accu chłodniejszy / bardziej „szary”; MB ~26°C + deszcz od popołudnia |

---

*Źródła: Meteoblue MultiModel + meteogram · Open-Meteo ICON w pipeline.*
