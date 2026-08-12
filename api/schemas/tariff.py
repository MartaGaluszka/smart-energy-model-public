from __future__ import annotations

from pydantic import BaseModel


class TariffRates(BaseModel):
    valid_from: str
    valid_to: str | None = None
    tariff_name: str = 'G12w'
    price_zone1_day: float
    price_zone2_night: float
    distribution_zone1: float | None = None
    distribution_zone2: float | None = None
    subscription_fee_monthly: float | None = None
    power_fee_monthly: float | None = None
    oze_fee_kwh: float | None = None
    vat_mode: str = 'net'
    notes: str | None = None
    source: str = 'default'


class TariffRatesCreate(BaseModel):
    valid_from: str
    tariff_name: str = 'G12w'
    price_zone1_day: float
    price_zone2_night: float
    distribution_zone1: float | None = None
    distribution_zone2: float | None = None
    subscription_fee_monthly: float | None = None
    power_fee_monthly: float | None = None
    oze_fee_kwh: float | None = None
    vat_mode: str = 'net'
    notes: str | None = None
