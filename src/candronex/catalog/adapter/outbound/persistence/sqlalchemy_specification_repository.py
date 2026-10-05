from __future__ import annotations

from sqlalchemy.orm import Session

from candronex.catalog.adapter.outbound.persistence.models import (
    ServiceSpecificationModel,
)
from candronex.catalog.domain.repository import ServiceSpecificationRepository
from candronex.catalog.domain.service_specification import (
    ServiceCharacteristic,
    ServiceSpecification,
    ServiceType,
)
from candronex.platform.db import SessionFactory


def _decode(value_text: str, value_type: str) -> int | str:
    return int(value_text) if value_type == "int" else value_text


class SqlAlchemySpecificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find(self, service_type: ServiceType) -> ServiceSpecification | None:
        model = self._session.get(ServiceSpecificationModel, service_type.value)
        if model is None:
            return None
        return ServiceSpecification(
            service_type=ServiceType(model.service_type),
            name=model.name,
            characteristics=tuple(
                ServiceCharacteristic(c.name, _decode(c.value_text, c.value_type))
                for c in model.characteristics
            ),
        )


class SqlAlchemyCatalogUnitOfWork:
    specifications: ServiceSpecificationRepository

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyCatalogUnitOfWork":
        self._session = self._session_factory()
        self.specifications = SqlAlchemySpecificationRepository(self._session)
        return self

    def __exit__(self, *exc_info: object) -> None:
        assert self._session is not None
        self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        assert self._session is not None
        self._session.commit()
