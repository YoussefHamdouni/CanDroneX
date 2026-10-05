"""Identifiants échangés par tous les modules (noyau partagé)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from candronex.shared.errors import InvalidInput

_DRONE_ID = re.compile(r"^[A-Z0-9-]{3,32}$")
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@dataclass(frozen=True)
class ClientId:
    """Identifiant d'un client B2B, toujours déduit du jeton d'authentification."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise InvalidInput("L'identifiant du client est obligatoire.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DroneId:
    """Identifiant métier d'un drone, choisi par l'exploitant (ex. DRN-0231)."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _DRONE_ID.match(self.value):
            raise InvalidInput(
                "Le droneId doit contenir de 3 à 32 caractères parmi A-Z, 0-9 et '-'.",
                code="INVALID_DRONE_ID",
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CorrelationId:
    """Identifiant qui suit une opération de bout en bout (journaux, audit)."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CORRELATION_ID.match(self.value):
            raise InvalidInput("Identifiant de corrélation invalide.")

    @classmethod
    def new(cls) -> "CorrelationId":
        return cls(str(uuid.uuid4()))

    @classmethod
    def accept_or_new(cls, raw: str | None) -> "CorrelationId":
        """Retient l'identifiant fourni s'il est valide, sinon en génère un."""
        if raw and _CORRELATION_ID.match(raw):
            return cls(raw)
        return cls.new()

    def __str__(self) -> str:
        return self.value
