"""Dépendance FastAPI : identifie le client à partir du jeton porteur.

La plateforme ne dépend d'aucun module métier : l'authentificateur est fourni par la
racine de composition (container.py), qui y branche le module Identity & Access.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Header, Request

from candronex.platform.web.correlation import correlation_id_of
from candronex.shared.ids import ClientId


class TokenAuthenticator(Protocol):
    def authenticate(self, token: str, correlation_id: str = "") -> ClientId: ...


def get_client_id(
    request: Request,
    authorization: str | None = Header(default=None),
) -> ClientId:
    """Le ClientId vient toujours du jeton, jamais du corps de la requête (ADR-007)."""
    authenticator: TokenAuthenticator = request.app.state.client_authenticator
    correlation_id = correlation_id_of(request).value
    if not authorization or not authorization.lower().startswith("bearer "):
        # Refus consigné par le module Identity, comme tout autre refus d'accès.
        return authenticator.authenticate("", correlation_id)
    return authenticator.authenticate(authorization[len("bearer ") :].strip(), correlation_id)
