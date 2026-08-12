"""Taryfa (TA.5): GET/POST /tariff/rates — user_tariff_overrides + fallback tauron_tariff."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.errors import ApiError

from api.config import get_settings
from api.deps import get_current_user, get_db
from api.models import AppUser, UserTariffOverride
from api.schemas.tariff import TariffRates, TariffRatesCreate

router = APIRouter(prefix='/api/v1/tariff', tags=['tariff'], dependencies=[Depends(get_current_user)])


def _round2(value: float | None) -> float | None:
    """Ceny w `tauron_tariff` bywają w SQLite jako REAL z artefaktem zmiennoprzecinkowym
    (np. `30.169999999999998` zamiast `30.17`) — zaokrąglenie do groszy przy zwrocie z API
    czyści to przed pokazaniem w formularzu (grosze i tak są najmniejszą sensowną jednostką)."""
    return round(value, 2) if value is not None else None


def _fallback_global_rates() -> TariffRates | None:
    settings = get_settings()
    import os

    if not os.path.exists(settings.DATABASE_PATH):
        return None

    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT * FROM tauron_tariff
            WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?)
            ORDER BY valid_from DESC LIMIT 1
            """,
            (date.today().isoformat(), date.today().isoformat()),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return TariffRates(
        valid_from=row['valid_from'],
        valid_to=row['valid_to'],
        tariff_name=row['tariff_name'],
        price_zone1_day=_round2(row['price_zone1_day']),
        price_zone2_night=_round2(row['price_zone2_night']),
        distribution_zone1=_round2(row['distribution_zone1']),
        distribution_zone2=_round2(row['distribution_zone2']),
        subscription_fee_monthly=_round2(row['subscription_fee_monthly']),
        power_fee_monthly=_round2(row['power_fee_monthly']),
        oze_fee_kwh=row['oze_fee_kwh'],
        vat_mode='net',
        notes=row['notes'],
        source='tauron_tariff (global default)',
    )


@router.get('/rates', response_model=TariffRates, summary='Aktualne/ostatnie stawki użytkownika (lub domyślne globalne)')
def get_rates(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> TariffRates:
    override = (
        db.query(UserTariffOverride)
        .filter(UserTariffOverride.user_id == current_user.id)
        .order_by(UserTariffOverride.valid_from.desc(), UserTariffOverride.id.desc())
        .first()
    )
    if override is not None:
        return _override_to_response(override)

    fallback = _fallback_global_rates()
    if fallback is not None:
        return fallback

    return TariffRates(
        valid_from=date.today().isoformat(),
        price_zone1_day=0.85,
        price_zone2_night=0.45,
        source='hardcoded_default',
        notes='Brak stawek w bazie — wartości placeholder, ustaw prawdziwe przez POST /tariff/rates',
    )


def _as_iso(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _override_to_response(override: UserTariffOverride) -> TariffRates:
    return TariffRates(
        valid_from=_as_iso(override.valid_from) or date.today().isoformat(),
        valid_to=_as_iso(override.valid_to),
        tariff_name=override.tariff_name,
        price_zone1_day=override.price_zone1_day,
        price_zone2_night=override.price_zone2_night,
        distribution_zone1=override.distribution_zone1,
        distribution_zone2=override.distribution_zone2,
        subscription_fee_monthly=override.subscription_fee_monthly,
        power_fee_monthly=override.power_fee_monthly,
        oze_fee_kwh=override.oze_fee_kwh,
        vat_mode=override.vat_mode,
        notes=override.notes,
        source='user_tariff_overrides',
    )


@router.post('/rates', response_model=TariffRates, status_code=201, summary='Zapis stawek (z faktury)')
def create_rates(
    body: TariffRatesCreate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TariffRates:
    # Upsert po (user_id, valid_from): poprawka literówki dla TEJ SAMEJ daty "Ważne od"
    # ma nadpisać istniejący wpis, nie dopisywać kolejny. Nowy wiersz historii powstaje
    # tylko wtedy, gdy faktycznie zmienia się okres obowiązywania stawek (inne valid_from).
    existing = (
        db.query(UserTariffOverride)
        .filter(
            UserTariffOverride.user_id == current_user.id,
            UserTariffOverride.valid_from == body.valid_from,
        )
        .order_by(UserTariffOverride.id.desc())
        .first()
    )
    if existing is not None:
        for field, value in body.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _override_to_response(existing)

    override = UserTariffOverride(user_id=current_user.id, **body.model_dump())
    db.add(override)
    db.commit()
    db.refresh(override)
    return _override_to_response(override)


@router.get(
    '/rates/history',
    response_model=list[TariffRates],
    summary='Wszystkie zapisane taryfy użytkownika (do zmiany w ciągu roku), najnowsza pierwsza',
)
def get_rates_history(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TariffRates]:
    overrides = (
        db.query(UserTariffOverride)
        .filter(UserTariffOverride.user_id == current_user.id)
        .order_by(UserTariffOverride.valid_from.desc(), UserTariffOverride.id.desc())
        .all()
    )
    return [_override_to_response(o) for o in overrides]


@router.delete(
    '/rates/{valid_from}',
    status_code=204,
    response_model=None,
    summary='Usuwa zapisaną taryfę dla danej daty "Ważne od"',
)
def delete_rates(
    valid_from: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    override = (
        db.query(UserTariffOverride)
        .filter(UserTariffOverride.user_id == current_user.id, UserTariffOverride.valid_from == valid_from)
        .first()
    )
    if override is None:
        raise ApiError(404, 'TARIFF_NOT_FOUND', f'Brak zapisanej taryfy dla daty {valid_from}')
    db.delete(override)
    db.commit()
