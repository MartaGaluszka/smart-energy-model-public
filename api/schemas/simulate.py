from __future__ import annotations

from pydantic import BaseModel

from api.schemas.tariff import TariffRatesCreate


class SimulateBillRequest(BaseModel):
    period_start: str
    period_end: str
    rates_override: TariffRatesCreate | None = None


class SimulateBillResponse(BaseModel):
    # T2.7: netto i brutto (VAT 23%, doliczony na końcu do sumy — jak na fakturze Tauron)
    # zwracane RAZEM, żeby UI pokazywał obie kwoty naraz bez przełącznika i drugiego
    # zapytania do API (uprościło to też ekran — mniej stanu, mniej okazji do błędów UX).
    cost_no_pv_net_pln: float
    cost_no_pv_gross_pln: float
    cost_with_pv_net_pln: float
    cost_with_pv_gross_pln: float
    savings_net_pln: float
    savings_gross_pln: float
    # T2.6: mini tabela kWh "dach / sieć / oddanie" — produkcja z paneli (dach), import z sieci,
    # eksport (oddanie) do sieci.
    production_kwh: float
    import_kwh: float
    export_kwh: float
    self_consumed_kwh: float
    deposit_credit_pln: float | None = None
