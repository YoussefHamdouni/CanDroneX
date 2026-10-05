"""Objets valeur du contexte Ordering."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Union

from candronex.shared.errors import InvalidInput

_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7E]{1,255}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")

CharacteristicValue = Union[int, str]


@dataclass(frozen=True)
class ServiceOrderId:
    value: uuid.UUID

    @classmethod
    def new(cls) -> "ServiceOrderId":
        return cls(uuid.uuid4())

    @classmethod
    def parse(cls, raw: str) -> "ServiceOrderId":
        try:
            return cls(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError):
            raise InvalidInput("Identifiant de commande invalide.") from None

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class OrderItemId:
    value: uuid.UUID

    @classmethod
    def new(cls) -> "OrderItemId":
        return cls(uuid.uuid4())

    @classmethod
    def parse(cls, raw: str) -> "OrderItemId":
        try:
            return cls(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError):
            raise InvalidInput("Identifiant d'élément invalide.") from None

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class IdempotencyKey:
    """Clé fournie par le client pour identifier une demande logique (ADR-006)."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _IDEMPOTENCY_KEY.match(self.value):
            raise InvalidInput(
                "L'en-tête Idempotency-Key doit contenir de 1 à 255 caractères visibles.",
                code="INVALID_IDEMPOTENCY_KEY",
            )


@dataclass(frozen=True)
class RequestFingerprint:
    """Empreinte SHA-256 du contenu normalisé de la requête de commande."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _FINGERPRINT.match(self.value):
            raise InvalidInput("Empreinte de requête invalide.")


class OrderItemAction(str, Enum):
    ADD = "add"  # delete (UC-09) et modify viendront plus tard


class ItemStatus(str, Enum):
    RECEIVED = "RECEIVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"  # modélisé (UC-15)
    COMPENSATED = "COMPENSATED"  # modélisé (UC-15)

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_ITEM_STATUSES


_TERMINAL_ITEM_STATUSES = frozenset(
    {ItemStatus.COMPLETED, ItemStatus.FAILED, ItemStatus.CANCELLED, ItemStatus.COMPENSATED}
)


class OrderStatus(str, Enum):
    RECEIVED = "RECEIVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Characteristic:
    name: str
    value: CharacteristicValue


@dataclass(frozen=True)
class CharacteristicSnapshot:
    """Copie figée des caractéristiques, prise du catalogue à la soumission."""

    characteristics: tuple[Characteristic, ...]

    def __post_init__(self) -> None:
        if not self.characteristics:
            raise InvalidInput("Un élément de commande doit porter ses caractéristiques.")
        names = [c.name for c in self.characteristics]
        if len(names) != len(set(names)):
            raise InvalidInput("Les caractéristiques d'un élément doivent être uniques.")


@dataclass(frozen=True)
class FailureCause:
    code: str
    message: str
