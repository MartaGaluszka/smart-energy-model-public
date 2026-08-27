"""
Realistyczna symulacja SoC baterii z wykorzystaniem prognozy PV i profilu zużycia.

Używane w battery_planner.py do generowania planu 24h.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BatterySimulationParams:
    """Parametry baterii do symulacji."""
    
    capacity_kwh: float = 10.36  # Pojemność nominalna [kWh]
    efficiency_charge: float = 0.93  # Sprawność ładowania (93%)
    efficiency_discharge: float = 0.93  # Sprawność rozładowania (93%)
    max_charge_power_kw: float = 5.0  # Maksymalna moc ładowania [kW]
    max_discharge_power_kw: float = 5.0  # Maksymalna moc rozładowania [kW]


def simulate_realistic_soc(
    pv_forecast_kwh: list[float],  # 24h prognoza PV [kWh per hour]
    load_profile_kwh: list[float],  # 24h profil zużycia [kWh per hour]
    soc_start_percent: float,  # SoC na start [%]
    soc_min_percent: float,  # Minimalne SoC (rezerwa) [%]
    soc_target_percent: float,  # Docelowe SoC (max ładowanie) [%]
    force_charge_hours: list[int] | None = None,  # Godziny ForceCharge z sieci
    params: BatterySimulationParams | None = None,
) -> list[float]:
    """Symuluje trajektorię SoC przez 24h z uwzględnieniem PV, zużycia i ładowania.

    Logika:
    1. Dla każdej godziny: bilans = PV - load
    2. Jeśli bilans > 0 → ładuj baterię (do soc_target)
    3. Jeśli bilans < 0 → rozładuj baterię (do soc_min) lub import z sieci
    4. Jeśli force_charge → ładuj z sieci do soc_target (tania strefa)

    Args:
        pv_forecast_kwh: Lista 24 wartości PV [kWh] (0-23)
        load_profile_kwh: Lista 24 wartości load [kWh] (0-23)
        soc_start_percent: SoC początkowy [%]
        soc_min_percent: Rezerwa (nie rozładowuj poniżej) [%]
        soc_target_percent: Cel ładowania [%]
        force_charge_hours: Lista godzin, w których ForceCharge z sieci (np. [22, 23, 0, 1])
        params: Parametry baterii (capacity, efficiency)

    Returns:
        Lista 24 wartości SoC [%] (0-23) — stan na KONIEC każdej godziny
    """
    if params is None:
        params = BatterySimulationParams()

    if force_charge_hours is None:
        force_charge_hours = []

    if len(pv_forecast_kwh) != 24 or len(load_profile_kwh) != 24:
        raise ValueError("pv_forecast_kwh i load_profile_kwh muszą mieć długość 24")

    soc_trajectory = []
    soc_current = soc_start_percent

    for hour in range(24):
        pv_kwh = pv_forecast_kwh[hour]
        load_kwh = load_profile_kwh[hour]

        # Bilans energii: net = PV - load
        net_kwh = pv_kwh - load_kwh

        # Konwersja % SoC → kWh
        soc_current_kwh = (soc_current / 100.0) * params.capacity_kwh
        soc_min_kwh = (soc_min_percent / 100.0) * params.capacity_kwh
        soc_target_kwh = (soc_target_percent / 100.0) * params.capacity_kwh

        # Jeśli ForceCharge — ładuj z sieci do celu
        if hour in force_charge_hours:
            # Ładowanie z sieci: do soc_target, z ograniczeniem mocy
            charge_needed_kwh = soc_target_kwh - soc_current_kwh
            charge_possible_kwh = min(charge_needed_kwh, params.max_charge_power_kw)
            soc_next_kwh = soc_current_kwh + (charge_possible_kwh * params.efficiency_charge)
            soc_next_kwh = min(soc_target_kwh, soc_next_kwh)

        elif net_kwh > 0:
            # Nadwyżka PV → ładuj baterię
            charge_kwh = min(net_kwh, params.max_charge_power_kw)
            soc_next_kwh = soc_current_kwh + (charge_kwh * params.efficiency_charge)
            soc_next_kwh = min(soc_target_kwh, soc_next_kwh)

        else:
            # Niedobór energii → rozładuj baterię (lub import z sieci)
            deficit_kwh = abs(net_kwh)
            discharge_kwh = min(deficit_kwh, params.max_discharge_power_kw)
            discharge_available_kwh = max(0.0, soc_current_kwh - soc_min_kwh)
            discharge_actual_kwh = min(discharge_kwh, discharge_available_kwh)

            soc_next_kwh = soc_current_kwh - (discharge_actual_kwh / params.efficiency_discharge)
            soc_next_kwh = max(soc_min_kwh, soc_next_kwh)

        # Konwersja kWh → %
        soc_next_percent = (soc_next_kwh / params.capacity_kwh) * 100.0
        soc_next_percent = max(0.0, min(100.0, soc_next_percent))

        soc_trajectory.append(soc_next_percent)
        soc_current = soc_next_percent

    return soc_trajectory


def annotate_soc_with_notes(
    soc_trajectory: list[float],
    pv_forecast_kwh: list[float],
    load_profile_kwh: list[float],
    soc_min_percent: float,
    zones: list[int],  # G12w zones (1=peak, 2=cheap)
) -> list[str]:
    """Generuje krótkie notatki per godzina opisujące co się dzieje z baterią.

    Args:
        soc_trajectory: Lista SoC [%] per godzina
        pv_forecast_kwh: PV forecast per godzina
        load_profile_kwh: Load profile per godzina
        soc_min_percent: Minimalne SoC (rezerwa)
        zones: G12w zones per godzina

    Returns:
        Lista 24 stringów z notatkami (np. "Ładowanie z PV", "Rozładowanie do domu")
    """
    notes = []
    for h in range(24):
        pv = pv_forecast_kwh[h]
        load = load_profile_kwh[h]
        soc = soc_trajectory[h]
        zone = zones[h]

        net = pv - load
        zone_label = "tania" if zone == 2 else "droga"

        if net > 0.5:
            notes.append(f"Ładowanie z PV (+{net:.1f} kWh), {zone_label}")
        elif net < -0.5:
            if soc > soc_min_percent + 5:
                notes.append(f"Rozładowanie baterii ({abs(net):.1f} kWh), {zone_label}")
            else:
                notes.append(f"Import z sieci (SoC niskie), {zone_label}")
        else:
            notes.append(f"Balans PV≈load, {zone_label}")

    return notes
