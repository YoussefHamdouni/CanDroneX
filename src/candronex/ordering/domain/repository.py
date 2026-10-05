from __future__ import annotations

from typing import Protocol

from candronex.ordering.domain.service_order import ServiceOrder
from candronex.ordering.domain.values import IdempotencyKey, ServiceOrderId
from candronex.shared.ids import ClientId


class ServiceOrderRepository(Protocol):
    """Toute lecture exige le client propriétaire (ADR-007)."""

    def add(self, order: ServiceOrder) -> None: ...

    def get(self, client_id: ClientId, order_id: ServiceOrderId) -> ServiceOrder | None: ...

    def find_by_idempotency_key(
        self, client_id: ClientId, key: IdempotencyKey
    ) -> ServiceOrder | None: ...

    def update(self, order: ServiceOrder) -> None:
        """Enregistre les transitions. Lève ConcurrentModification si la version a changé."""
        ...
