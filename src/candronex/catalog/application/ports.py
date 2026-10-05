from __future__ import annotations

from typing import Callable, Protocol

from candronex.catalog.domain.repository import ServiceSpecificationRepository


class CatalogUnitOfWork(Protocol):
    specifications: ServiceSpecificationRepository

    def __enter__(self) -> "CatalogUnitOfWork": ...
    def __exit__(self, *exc_info: object) -> None: ...
    def commit(self) -> None: ...


CatalogUnitOfWorkFactory = Callable[[], CatalogUnitOfWork]
