from __future__ import annotations

from typing import Protocol

from candronex.catalog.domain.service_specification import (
    ServiceSpecification,
    ServiceType,
)


class ServiceSpecificationRepository(Protocol):
    def find(self, service_type: ServiceType) -> ServiceSpecification | None: ...
