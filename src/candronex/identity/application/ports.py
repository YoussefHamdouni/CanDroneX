from __future__ import annotations

from typing import Callable, Protocol

from candronex.identity.domain.repository import ClientRepository, CredentialRepository


class IdentityUnitOfWork(Protocol):
    credentials: CredentialRepository
    clients: ClientRepository

    def __enter__(self) -> "IdentityUnitOfWork": ...
    def __exit__(self, *exc_info: object) -> None: ...
    def commit(self) -> None: ...


IdentityUnitOfWorkFactory = Callable[[], IdentityUnitOfWork]
