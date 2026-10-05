"""Ports de sortie de la couche application d'Ordering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Union

from candronex.ordering.domain.repository import ServiceOrderRepository


@dataclass(frozen=True)
class ActivationRequest:
    """Demande d'activation d'un élément. Types simples : prête à traverser un réseau en Phase 2."""

    client_id: str
    order_id: str
    item_id: str
    drone_id: str
    service_type: str
    characteristics: tuple[tuple[str, Union[int, str]], ...]
    correlation_id: str


class ActivationRequester(Protocol):
    """Déclaré par Ordering, implémenté par la simulation (Phase 1) puis par Activation (ADR-005)."""

    def request_activation(self, request: ActivationRequest) -> None: ...


class OrderingUnitOfWork(Protocol):
    orders: ServiceOrderRepository

    def __enter__(self) -> "OrderingUnitOfWork": ...
    def __exit__(self, *exc_info: object) -> None: ...

    def commit(self) -> None:
        """Lève DuplicateIdempotencyKey, DuplicateItem ou ConcurrentModification au besoin."""
        ...


OrderingUnitOfWorkFactory = Callable[[], OrderingUnitOfWork]
