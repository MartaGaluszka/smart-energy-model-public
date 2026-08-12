-- Profil godzinowy zużycia i produkcji
-- Pokazuje średnią moc dla każdej godziny dnia
-- Przydatne do analizy taryfy G12w (strefy czasowe)

SELECT 
    CAST(STRFTIME('%H', timestamp) AS INTEGER) as godzina,
    
    -- Średnia moc PV
    ROUND(AVG(pv_power_kw), 3) as srednia_pv_kw,
    
    -- Średnie zużycie
    ROUND(AVG(load_power_kw), 3) as srednie_zuzycie_kw,
    
    -- Średnia moc baterii (+ ładowanie, - rozładowanie)
    ROUND(AVG(battery_power_kw), 3) as srednia_moc_baterii_kw,
    
    -- Strefa G12w (uproszczenie: bez weekendów/świąt — pełna logika w g12w_tariff.py)
    CASE
        WHEN CAST(STRFTIME('%w', timestamp) AS INTEGER) IN (0, 6) THEN 'Pozaszczyt (weekend)'
        WHEN CAST(STRFTIME('%H', timestamp) AS INTEGER) BETWEEN 6 AND 12 THEN 'Szczyt (droższa)'
        WHEN CAST(STRFTIME('%H', timestamp) AS INTEGER) BETWEEN 15 AND 21 THEN 'Szczyt (droższa)'
        ELSE 'Pozaszczyt (tańsza)'
    END as strefa_g12w,
    
    -- Liczba pomiarów
    COUNT(*) as liczba_pomiarow

FROM foxess_data
GROUP BY godzina
ORDER BY godzina;
