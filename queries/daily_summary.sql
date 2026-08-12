-- Dzienne podsumowanie produkcji i zużycia
-- To zapytanie pokazuje bilans energetyczny dla każdego dnia

SELECT 
    DATE(timestamp) as dzien,
    
    -- Produkcja fotowoltaiki
    ROUND(SUM(pv_energy_kwh), 2) as produkcja_pv_kwh,
    
    -- Zużycie energii
    ROUND(SUM(load_energy_kwh), 2) as zuzycie_kwh,
    
    -- Wymiana z siecią
    ROUND(SUM(grid_import_kwh), 2) as import_z_sieci_kwh,
    ROUND(SUM(grid_export_kwh), 2) as eksport_do_sieci_kwh,
    
    -- Bilans
    ROUND(SUM(grid_export_kwh) - SUM(grid_import_kwh), 2) as bilans_sieci_kwh,
    
    -- Średni stan baterii
    ROUND(AVG(battery_soc_percent), 1) as sredni_soc_percent,
    
    -- Autokonsumpcja (ile własnej energii zużyłeś)
    ROUND((SUM(pv_energy_kwh) - SUM(grid_export_kwh)) / SUM(pv_energy_kwh) * 100, 1) 
        as autokonsumpcja_percent,
    
    -- Samowystarczalność (jak bardzo jesteś niezależny od sieci)
    ROUND((SUM(load_energy_kwh) - SUM(grid_import_kwh)) / SUM(load_energy_kwh) * 100, 1)
        as samowystarczalnosc_percent

FROM foxess_data
GROUP BY DATE(timestamp)
ORDER BY dzien DESC;
