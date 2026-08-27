"""SQLAlchemy ORM — nowe tabele appki mobilnej (§13 PROJEKT_APLIKACJA_MOBILNA.md).

Mirror `db/init/002_app_tables.sql` (Postgres). Kolumny/typy dobrane tak, by
działały identycznie na SQLite (lokalny dev) i Postgresie (Docker).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class AppUser(Base):
    __tablename__ = 'app_users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    secrets: Mapped[list['UserSecret']] = relationship(back_populates='user', cascade='all, delete-orphan')


class UserSecret(Base):
    __tablename__ = 'user_secrets'
    __table_args__ = (UniqueConstraint('user_id', 'provider', name='uq_user_secrets_user_provider'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default='foxess', nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    device_sn_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped['AppUser'] = relationship(back_populates='secrets')


class UserTariffOverride(Base):
    __tablename__ = 'user_tariff_overrides'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, index=True)
    valid_from: Mapped[str] = mapped_column(String(10), nullable=False)
    valid_to: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tariff_name: Mapped[str] = mapped_column(String(20), default='G12w', nullable=False)
    price_zone1_day: Mapped[float] = mapped_column(Float, nullable=False)
    price_zone2_night: Mapped[float] = mapped_column(Float, nullable=False)
    distribution_zone1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distribution_zone2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    subscription_fee_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    power_fee_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oze_fee_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vat_mode: Mapped[str] = mapped_column(String(10), default='net', nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HouseholdEvent(Base):
    __tablename__ = 'household_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, index=True)
    event_date: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), default='neutral', nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RoiAssumptions(Base):
    __tablename__ = 'roi_assumptions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    capex_pln: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    battery_capex_pln: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opex_pln_year: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    inflation_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    seller_baseline_pln_year: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BatteryStrategySettings(Base):
    __tablename__ = 'battery_strategy_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    soc_min_percent: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    soc_target_percent: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    efficiency_pct: Mapped[float] = mapped_column(Float, default=93.0, nullable=False)
    price_zone1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_zone2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    season: Mapped[str] = mapped_column(String(10), default='auto', nullable=False)
    battery_capacity_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ac_power_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Notification(Base):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, index=True)
    notif_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PushSubscription(Base):
    __tablename__ = 'push_subscriptions'
    __table_args__ = (UniqueConstraint('user_id', 'token', name='uq_push_subscriptions_user_token'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), default='android', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AdviceEvent(Base):
    __tablename__ = 'advice_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('app_users.id', ondelete='CASCADE'), nullable=False, index=True)
    event_date: Mapped[str] = mapped_column(String(10), nullable=False)
    advice_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    was_actionable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
