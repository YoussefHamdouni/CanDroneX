"""Traduction centralisée des erreurs en réponses Problem Details (RFC 9457)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from candronex.platform.web.correlation import correlation_id_of
from candronex.shared.errors import (
    BusinessRuleViolation,
    CanDroneXError,
    ConflictError,
    InvalidInput,
    ResourceNotFound,
    ServiceUnavailable,
    Unauthenticated,
)

log = logging.getLogger("candronex.errors")

PROBLEM_JSON = "application/problem+json"
PROBLEM_BASE = "https://candronex.example/problems/"

# Ordre important : la première famille qui correspond l'emporte.
_STATUS_BY_FAMILY: list[tuple[type[CanDroneXError], int]] = [
    (InvalidInput, 400),
    (Unauthenticated, 401),
    (ResourceNotFound, 404),
    (ConflictError, 409),
    (BusinessRuleViolation, 422),
    (ServiceUnavailable, 503),
]


def _problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": PROBLEM_BASE + code.lower().replace("_", "-"),
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "correlationId": correlation_id_of(request).value,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _status_for(error: CanDroneXError) -> int:
    for family, status in _STATUS_BY_FAMILY:
        if isinstance(error, family):
            return status
    return 500


async def _handle_domain_error(request: Request, error: CanDroneXError) -> JSONResponse:
    status = _status_for(error)
    if status == 500:
        log.error("erreur interne", exc_info=error)
        return _internal(request)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return _problem(
        request,
        status=status,
        code=error.code,
        title=error.title,
        detail=error.detail,
        headers=headers,
    )


async def _handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    # FastAPI répond 422 par défaut; 422 est réservé aux règles métier (ADR-004).
    details = [
        {
            "field": ".".join(str(part) for part in err.get("loc", ()) if part != "body"),
            "reason": err.get("msg", "invalide"),
        }
        for err in error.errors()
    ]
    return _problem(
        request,
        status=400,
        code="INVALID_INPUT",
        title="Requête invalide",
        detail="Un ou plusieurs champs sont absents ou invalides.",
        errors=details,
    )


async def _handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(error.status_code, "HTTP_ERROR")
    return _problem(
        request,
        status=error.status_code,
        code=code,
        title="Erreur HTTP",
        detail=str(error.detail),
    )


async def _handle_database_unavailable(request: Request, error: OperationalError) -> JSONResponse:
    log.error("base de données indisponible", exc_info=error)
    return _problem(
        request,
        status=503,
        code="SERVICE_UNAVAILABLE",
        title="Service indisponible",
        detail="La base de données est momentanément indisponible. Réessayez plus tard.",
    )


def _internal(request: Request) -> JSONResponse:
    # Aucun détail technique n'est renvoyé au client; le détail est journalisé.
    return _problem(
        request,
        status=500,
        code="INTERNAL_ERROR",
        title="Erreur interne",
        detail="Une erreur imprévue est survenue.",
    )


async def _handle_unexpected(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, DBAPIError) and getattr(error, "connection_invalidated", False):
        return await _handle_database_unavailable(request, error)  # type: ignore[arg-type]
    log.error("erreur imprévue", exc_info=error)
    return _internal(request)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CanDroneXError, _handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)  # type: ignore[arg-type]
    app.add_exception_handler(OperationalError, _handle_database_unavailable)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected)
