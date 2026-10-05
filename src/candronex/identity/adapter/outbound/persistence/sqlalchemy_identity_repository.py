from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from candronex.identity.adapter.outbound.persistence.models import (
    ApiCredentialModel,
    B2BClientModel,
)
from candronex.identity.domain.b2b_client import (
    ApiCredential,
    B2BClient,
    ClientStatus,
    CredentialStatus,
)
from candronex.identity.domain.repository import ClientRepository, CredentialRepository
from candronex.platform.db import SessionFactory
from candronex.shared.ids import ClientId


class SqlAlchemyCredentialRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_token_hash(self, token_hash: str) -> ApiCredential | None:
        model = self._session.scalar(
            select(ApiCredentialModel).where(ApiCredentialModel.token_hash == token_hash)
        )
        if model is None:
            return None
        return ApiCredential(
            credential_id=model.id,
            client_id=ClientId(model.client_id),
            token_hash=model.token_hash,
            status=CredentialStatus(model.status),
        )


class SqlAlchemyClientRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find(self, client_id: ClientId) -> B2BClient | None:
        model = self._session.get(B2BClientModel, client_id.value)
        if model is None:
            return None
        return B2BClient(
            client_id=ClientId(model.client_id),
            name=model.name,
            status=ClientStatus(model.status),
        )


class SqlAlchemyIdentityUnitOfWork:
    credentials: CredentialRepository
    clients: ClientRepository

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyIdentityUnitOfWork":
        self._session = self._session_factory()
        self.credentials = SqlAlchemyCredentialRepository(self._session)
        self.clients = SqlAlchemyClientRepository(self._session)
        return self

    def __exit__(self, *exc_info: object) -> None:
        assert self._session is not None
        self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        assert self._session is not None
        self._session.commit()
