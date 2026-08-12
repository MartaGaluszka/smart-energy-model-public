-- Porównanie kosztów: Prognoza Tauron vs Rzeczywistość
-- To zapytanie jest KLUCZOWE dla Twojego projektu!
-- Pokazuje oszczędności dzięki systemowi PV + bateria

WITH daily_consumption AS (
    -- Rzeczywiste dzienne zużycie z podziałem na strefy G12w
    SELECT 
        DATE(timestamp) as dzien,
        
        -- Strefa dzienna (6-13, 15-22)
        SUM(CASE 
            WHEN CAST(STRFTIME('%H', timestamp) AS INTEGER) BETWEEN 6 AND 12 
                OR CAST(STRFTIME('%H', timestamp) AS INTEGER) BETWEEN 15 AND 21
            THEN grid_import_kwh 
            ELSE 0 
        END) as import_strefa_dzienna,
        
        -- Strefa nocna (22-6, 13-15)
        SUM(CASE 
            WHEN CAST(STRFTIME('%H', timestamp) AS INTEGER) BETWEEN 13 AND 14
                OR CAST(STRFTIME('%H', timestamp) AS INTEGER) < 6
                OR CAST(STRFTIME('%H', timestamp) AS INTEGER) >= 22
            THEN grid_import_kwh 
            ELSE 0 
        END) as import_strefa_nocna,
        
        SUM(load_energy_kwh) as zuzycie_calkowite,
        SUM(pv_energy_kwh) as produkcja_pv,
        SUM(grid_export_kwh) as eksport_do_sieci
        
    FROM foxess_data
    GROUP BY DATE(timestamp)
),

costs AS (
    -- Obliczenie kosztów z aktualnym cennikiem
    SELECT 
        dc.*,
        
        -- Pobranie cennika
        t.price_zone1_day,
        t.price_zone2_night,
        t.distribution_zone1,
        t.distribution_zone2,
        
        -- Koszt rzeczywisty (z PV + bateria)
        ROUND(
            (dc.import_strefa_dzienna * (t.price_zone1_day + t.distribution_zone1)) +
            (dc.import_strefa_nocna * (t.price_zone2_night + t.distribution_zone2)),
            2
        ) as koszt_rzeczywisty,
        
        -- Koszt gdyby nie było PV (baseline - całe zużycie z sieci)
        ROUND(
            -- Założenie: 70% zużycia w dzień, 30% w nocy (typowy profil)
            (dc.zuzycie_calkowite * 0.7 * (t.price_zone1_day + t.distribution_zone1)) +
            (dc.zuzycie_calkowite * 0.3 * (t.price_zone2_night + t.distribution_zone2)),
            2
        ) as koszt_baseline
        
    FROM daily_consumption dc
    CROSS JOIN tauron_tariff t
    WHERE t.tariff_name = 'G12w'
        AND dc.dzien >= t.valid_from
        AND (t.valid_to IS NULL OR dc.dzien <= t.valid_to)
)

-- Finalne porównanie
SELECT 
    dzien,
    zuzycie_calkowite,
    produkcja_pv,
    import_strefa_dzienna + import_strefa_nocna as import_calkowity,
    eksport_do_sieci,
    
    koszt_baseline as koszt_bez_pv_zl,
    koszt_rzeczywisty as koszt_z_pv_zl,
    
    ROUND(koszt_baseline - koszt_rzeczywisty, 2) as oszczednosci_zl,
    ROUND((koszt_baseline - koszt_rzeczywisty) / koszt_baseline * 100, 1) as oszczednosci_percent,
    
    -- Autokonsumpcja
    ROUND((produkcja_pv - eksport_do_sieci) / produkcja_pv * 100, 1) as autokonsumpcja_percent

FROM costs
WHERE koszt_baseline > 0  -- Pomijamy dni bez danych
ORDER BY dzien DESC;
