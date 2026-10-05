"""Middleware de corrélation : un identifiant par requête, propagé et renvoyé."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from candronex.platform.logging_config import correlation_id_var
from candronex.shared.ids import CorrelationId

HEADER = "X-Correlation-Id"
log = logging.getLogger("candronex.http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = CorrelationId.accept_or_new(request.headers.get(HEADER))
        request.state.correlation_id = correlation_id
        token = correlation_id_var.set(correlation_id.value)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[HEADER] = correlation_id.value
            log.info(
                "[adapter.inbound] requête traitée",
                extra={
                    "fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "durationMs": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            return response
        finally:
            correlation_id_var.reset(token)


def correlation_id_of(request: Request) -> CorrelationId:
    value = getattr(request.state, "correlation_id", None)
    return value if isinstance(value, CorrelationId) else CorrelationId.new()
