from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from enum import Enum

from candronex.shared.ids import ClientId


class ClientStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class CredentialStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class B2BClient:
    client_id: ClientId
    name: str
    status: ClientStatus

    @property
    def is_active(self) -> bool:
        return self.status is ClientStatus.ACTIVE


@dataclass(frozen=True)
class ApiCredential:
    """Information d'accès d'un client. Seul le hachage du jeton est conservé."""

    credential_id: uuid.UUID
    client_id: ClientId
    token_hash: str
    status: CredentialStatus

    @property
    def is_usable(self) -> bool:
        return self.status is CredentialStatus.ACTIVE


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
