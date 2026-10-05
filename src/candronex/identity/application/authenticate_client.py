from __future__ import annotations

import logging
from typing import NoReturn

from candronex.audit.api import AuditLog, AuditRecord
from candronex.identity.api import AuthenticationFailed
from candronex.identity.application.ports import IdentityUnitOfWorkFactory
from candronex.identity.domain.b2b_client import hash_token
from candronex.shared.ids import ClientId

log = logging.getLogger(__name__)

_GENERIC = "Jeton invalide, expiré ou révoqué."


class ClientAuthenticationService:
    """Implémente ClientAuthenticator (interface publiée du module)."""

    def __init__(self, uow_factory: IdentityUnitOfWorkFactory, audit_log: AuditLog) -> None:
        self._uow_factory = uow_factory
        self._audit_log = audit_log

    def authenticate(self, token: str, correlation_id: str = "") -> ClientId:
        if not token:
            self._deny("MISSING_TOKEN", correlation_id)
        with self._uow_factory() as uow:
            credential = uow.credentials.find_by_token_hash(hash_token(token))
            if credential is None or not credential.is_usable:
                self._deny("INVALID_OR_REVOKED_TOKEN", correlation_id)
            client = uow.clients.find(credential.client_id)
            if client is None or not client.is_active:
                self._deny("INACTIVE_CLIENT", correlation_id)
            return client.client_id

    def _deny(self, reason: str, correlation_id: str) -> NoReturn:
        # Le jeton n'est jamais consigné, même haché.
        self._audit_log.record(
            AuditRecord(
                action="ACCESS_DENIED",
                actor_id="anonymous",
                resource_type="api",
                resource_id="-",
                correlation_id=correlation_id or "-",
                details={"reason": reason},
            )
        )
        log.info("[application] authentification refusée", extra={"fields": {"reason": reason}})
        raise AuthenticationFailed(_GENERIC)
