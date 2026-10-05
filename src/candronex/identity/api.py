"""Interface publiée du module Identity & Access."""

from __future__ import annotations

from typing import Protocol

from candronex.shared.errors import Unauthenticated
from candronex.shared.ids import ClientId


class AuthenticationFailed(Unauthenticated):
    code = "UNAUTHENTICATED"


class ClientAuthenticator(Protocol):
    def authenticate(self, token: str, correlation_id: str = "") -> ClientId:
        """Retourne le client du jeton, ou lève AuthenticationFailed (refus consigné)."""
        ...
