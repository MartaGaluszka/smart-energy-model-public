"""Wspólne schematy: ErrorResponse, HealthResponse (§12.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    code: str = 'ERROR'
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(examples=['ok'])
    version: str
    db_ok: bool


class ReadyResponse(BaseModel):
    status: str
    db_ok: bool
    model_ok: bool
    model_path: str
