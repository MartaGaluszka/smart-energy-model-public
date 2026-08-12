# SHAP — komentarze do wykresów

*Model: Random Forest produkcyjny (16 cech) · próbka testowa: 300 godzin dziennych · przykład peak PV: 5.00 kWh/h*

---

## Ranking cech — mean |SHAP|

*Średni bezwzględny wpływ każdej cechy na prognozę godzinową [kWh/h].*

Tabela sortuje cechy po **mean |SHAP|** — im wyżej, tym częściej i silniej dana zmienna przesuwa prognozę RF. Na szczycie listy są **zachmurzenie** i **geometria dnia** (`hours_until_sunset`, `sun_position`), a nie surowa **godzina kalendarzowa** (`hour` jest dopiero ~9. pozycji). To uzasadnia ablację 19→16 cech: model opiera się na fizyce PV i NWP, nie na sztywnym „o 12:00 zawsze X kWh".

## Summary bar — średni wpływ cech

*Długość słupka = mean |SHAP| · RF produkcyjny · holdout 20% dni · tylko is_daylight=1.*

Wykres słupkowy to **zagregowany** obraz ważności: ile średnio każda cecha „rusza" prognozą we wszystkich godzinach testowych. **Zachmurzenie** ma największy udział — zgodnie z intuicją (pochmurny dzień → mniej kWh). **Do zachodu** i **pozycja słońca** kodują kształt profilu dobowego (rano vs południe vs wieczór). **Radiacja** jest 4. na liście — ważna, ale częściowo skorelowana z chmurami i kątem słońca.

## Summary beeswarm — kierunek i rozkład wpływu

*Oś X: SHAP [kWh/h] · kolor: wartość cechy · każdy punkt = jedna godzina testowa.*

Każda kropka to **jedna godzina** ze zbioru testowego. Pozycja w poziomie: **SHAP > 0** podnosi prognozę względem średniej modelu, **SHAP < 0** ją obniża. Kolor pokazuje wartość cechy (np. czerwone = wysokie zachmurzenie). Widać, że przy **dużym zachmurzeniu** punkty idą w lewo (ujemny wpływ), a przy **wysokiej radiacji** — w prawo. Rozproszenie w pionie przy tej samej cechie oznacza **interakcje** z innymi zmiennymi (RF jest nieliniowy).

## Dependence — radiacja [W/m²]

*Oś Y: wpływ radiacji na prognozę · oś X: radiacja · kolor: interakcja z inną cechą.*

Pokazuje, jak ** sama wartość radiacji** przekłada się na korektę prognozy. Przy niskiej radiacji (<200 W/m²) wpływ jest bliski zera — model „wie", że i tak mało wyprodukujesz. Powyżej ~400 W/m² SHAP rośnie dodatnio: silne słońce podbija kWh/h. Kolor punktów sugeruje, że ten sam poziom radiacji może działać inaczej w zależności np. od chmur lub pory dnia.

## Dependence — zachmurzenie [%]

*Przy wysokim cloud_cover SHAP schodzi w minus — mniej energii niż przy czystym niebie.*

Najczytelniejsza monotonia: **im więcej chmur, tym niższa prognoza**. To potwierdza, że model nie ignoruje pogody na rzecz samego kalendarza — kluczowe dla dni burzowych (błąd operacyjny 21.07 w analizie błędów). Szeroki „garb" przy średnim zachmurzeniu to godziny, gdzie inne cechy (radiacja, pozycja słońca) modulują efekt chmur.

## Waterfall — skład prognozy w godzinie szczytu PV

*f(x) = E[f(X)] + Σ SHAP — przykład z najwyższą rzeczywistą PV w próbce testowej.*

Waterfall rozkłada **jedną konkretną prognozę** na sumę wpływów: start od **wartości bazowej** modelu (średnia), potem kolejne cechy dokładają lub odejmują kWh/h. Wybrano godzinę z **maksymalną rzeczywistą produkcją** w próbce — widać, które cechy „dociągnęły" prognozę w górę (słońce, radiacja) i co ją hamowało (chmury). Odpowiednik **force plot** w wersji statycznej pod slajd / PDF.

## Force plot (HTML) — ten sam przykład interaktywnie

*Czerwone = podbija prognozę · niebieskie = obniża · otwórz plik HTML w przeglądarce.*

Interaktywny **force plot** dla tej samej godziny co waterfall. Przydatny na obronie live (przewijanie, zoom). Plik: `reports/figures/shap_force_peak_hour.html`.

---

## Top 10 cech (mean |SHAP|)

| # | Cecha | mean \|SHAP\| |
|---|-------|-------------|
| 1 | Zachmurzenie [%] | 0.5656 |
| 2 | Do zachodu [h] | 0.5185 |
| 3 | Pozycja słońca | 0.2678 |
| 4 | Radiacja [W/m²] | 0.2606 |
| 5 | Wschód [h] | 0.0321 |
| 6 | Od wschodu [h] | 0.0294 |
| 7 | Wiatr [m/s] | 0.0193 |
| 8 | Wilgotność [%] | 0.0165 |
| 9 | Godzina | 0.0154 |
| 10 | Temperatura [°C] | 0.0125 |

