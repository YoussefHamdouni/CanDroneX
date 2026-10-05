"""Point de santé : vérifie l'application et la connexion à la base."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from candronex.platform.db import database_is_up

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> JSONResponse:
    if database_is_up(request.app.state.engine):
        return JSONResponse({"status": "UP", "database": "UP"}, status_code=200)
    return JSONResponse({"status": "DOWN", "database": "DOWN"}, status_code=503)
