"""Notifications (TA.8a): feed sugestii (in-app) + rejestracja push tokena."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import AppUser, PushSubscription
from api.schemas.notifications import NotificationResponse, PushTokenRequest, PushTokenResponse
from api.services.notifications_service import list_notifications

router = APIRouter(prefix='/api/v1/notifications', tags=['notifications'], dependencies=[Depends(get_current_user)])


@router.get('', response_model=list[NotificationResponse], summary='Feed sugestii baterii/magazynu na dashboard')
def get_notifications(
    current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[NotificationResponse]:
    rows = list_notifications(db, current_user.id)
    return [
        NotificationResponse(
            id=row.id,
            notif_type=row.notif_type,
            title=row.title,
            body=row.body,
            created_at=row.created_at.isoformat(),
            read_at=row.read_at.isoformat() if row.read_at else None,
        )
        for row in rows
    ]


@router.post('/push-token', response_model=PushTokenResponse, status_code=201, summary='Rejestracja FCM/APNs token')
def register_push_token(
    body: PushTokenRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PushTokenResponse:
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id, PushSubscription.token == body.token)
        .first()
    )
    if existing is None:
        db.add(PushSubscription(user_id=current_user.id, token=body.token, platform=body.platform))
        db.commit()

    return PushTokenResponse(status='registered')
