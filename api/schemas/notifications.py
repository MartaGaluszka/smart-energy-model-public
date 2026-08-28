from __future__ import annotations

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    notif_type: str
    title: str
    body: str
    created_at: str
    read_at: str | None = None


class PushTokenRequest(BaseModel):
    token: str
    platform: str = 'android'


class PushTokenResponse(BaseModel):
    status: str


class AdviceEventResponse(BaseModel):
    """T4.17 — wiersz audytu sugestii (walidacja roczna)."""

    id: int
    event_date: str
    advice_type: str
    was_actionable: bool
    payload_json: str | None = None
    created_at: str
