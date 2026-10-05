from __future__ import annotations

from candronex.catalog.api import CharacteristicView, ServiceSpecificationView
from candronex.catalog.application.ports import CatalogUnitOfWorkFactory
from candronex.catalog.domain.service_specification import ServiceType
from candronex.shared.errors import InvalidInput


class CatalogQueriesService:
    """Implémente CatalogQueries (interface publiée du module)."""

    def __init__(self, uow_factory: CatalogUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def find_specification(self, service_type: str) -> ServiceSpecificationView | None:
        try:
            parsed = ServiceType(service_type)
        except InvalidInput:
            return None
        with self._uow_factory() as uow:
            spec = uow.specifications.find(parsed)
        if spec is None:
            return None
        return ServiceSpecificationView(
            service_type=spec.service_type.value,
            name=spec.name,
            characteristics=tuple(
                CharacteristicView(c.name, c.value) for c in spec.characteristics
            ),
        )
