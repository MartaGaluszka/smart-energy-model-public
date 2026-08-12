"""Feed sugestii baterii (§9.6 / T4.18-T4.20) — LEKKI stub generatora.

Pełny generator (worker/cron analizujący plan G12w + prognozę PV codziennie,
T4.20) to zakres Fazy 4. Tutaj: jeśli użytkownik nie ma jeszcze żadnych
powiadomień, tworzymy jedną sugestię "cheap_window" na podstawie aktualnej
daty/godziny i `g12w_tariff`, żeby `GET /notifications` nie był pusty w
happy-path (zgodnie z DoD w ZADANIA_IMPLEMENTACJA_MOBILNA.md, sekcja Faza 4).
Wszystkie treści są doradcze — nigdy "wykonano automatycznie" (§9.6, T4.24).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from api.models import Notification


def ensure_seed_notification(db: Session, user_id: int) -> None:
    existing = db.query(Notification).filter(Notification.user_id == user_id).first()
    if existing is not None:
        return

    from src.optimization.g12w_tariff import tariff_summary

    notif = Notification(
        user_id=user_id,
        notif_type='cheap_window',
        title='Sugestia: tania strefa G12w',
        body=f'Sugestia doradcza — {tariff_summary()} Rozważ ładowanie magazynu w taniej strefie.',
        payload_json=None,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()


def list_notifications(db: Session, user_id: int) -> list[Notification]:
    ensure_seed_notification(db, user_id)
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
