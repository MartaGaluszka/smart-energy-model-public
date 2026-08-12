-- Miesięczne podsumowanie ROI
-- Agregacja danych miesięcznych do prezentacji

SELECT 
    STRFTIME('%Y-%m', timestamp) as miesiac,
    
    -- Energia
    ROUND(SUM(pv_energy_kwh), 0) as produkcja_pv_kwh,
    ROUND(SUM(load_energy_kwh), 0) as zuzycie_kwh,
    ROUND(SUM(grid_import_kwh), 0) as import_kwh,
    ROUND(SUM(grid_export_kwh), 0) as eksport_kwh,
    
    -- Wskaźniki
    ROUND(AVG(battery_soc_percent), 1) as sredni_soc_percent,
    ROUND((SUM(pv_energy_kwh) - SUM(grid_export_kwh)) / SUM(pv_energy_kwh) * 100, 1) 
        as autokonsumpcja_percent,
    
    -- Liczba dni z danymi
    COUNT(DISTINCT DATE(timestamp)) as liczba_dni,
    
    -- Średnia dzienna
    ROUND(SUM(pv_energy_kwh) / COUNT(DISTINCT DATE(timestamp)), 1) as srednia_produkcja_dzienna,
    ROUND(SUM(load_energy_kwh) / COUNT(DISTINCT DATE(timestamp)), 1) as srednie_zuzycie_dzienne

FROM foxess_data
GROUP BY STRFTIME('%Y-%m', timestamp)
ORDER BY miesiac DESC;
