"""Middleware request_id — T0.7c.

Wstawia/propaguje `X-Request-ID` na każde żądanie i udostępnia je przez
`request.state.request_id`, żeby handlery błędów mogły dołączyć je do
`ErrorResponse.request_id` (§12.1 kontraktu: `{ detail, code, request_id }`).
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

REQUEST_ID_HEADER = 'X-Request-ID'


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
