from __future__ import annotations

from typing import Protocol

from candronex.identity.domain.b2b_client import ApiCredential, B2BClient
from candronex.shared.ids import ClientId


class CredentialRepository(Protocol):
    def find_by_token_hash(self, token_hash: str) -> ApiCredential | None: ...


class ClientRepository(Protocol):
    def find(self, client_id: ClientId) -> B2BClient | None: ...
