"""Agrégat ServiceOrder et entité ServiceOrderItem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from candronex.ordering.domain.errors import (
    DuplicateItem,
    EmptyOrder,
    InvalidItemTransition,
    UnknownOrderItem,
)
from candronex.ordering.domain.values import (
    CharacteristicSnapshot,
    FailureCause,
    IdempotencyKey,
    ItemStatus,
    OrderItemAction,
    OrderItemId,
    OrderStatus,
    RequestFingerprint,
    ServiceOrderId,
)
from candronex.shared.ids import ClientId, CorrelationId, DroneId

# Transitions implémentées en Phase 1. CANCELLED, COMPENSATED (UC-15) et la reprise
# FAILED -> IN_PROGRESS (UC-10) sont modélisées mais pas encore permises.
_ALLOWED_TRANSITIONS: dict[ItemStatus, frozenset[ItemStatus]] = {
    ItemStatus.RECEIVED: frozenset({ItemStatus.IN_PROGRESS}),
    ItemStatus.IN_PROGRESS: frozenset({ItemStatus.COMPLETED, ItemStatus.FAILED}),
}


def derive_order_status(statuses: Iterable[ItemStatus]) -> OrderStatus:
    """Règles de dérivation de l'état global (§6.2), appliquées dans l'ordre."""
    statuses = list(statuses)
    if all(s is ItemStatus.RECEIVED for s in statuses):
        return OrderStatus.RECEIVED
    if any(not s.is_terminal for s in statuses):
        return OrderStatus.IN_PROGRESS
    if all(s is ItemStatus.COMPLETED for s in statuses):
        return OrderStatus.COMPLETED
    if any(s is ItemStatus.FAILED for s in statuses):
        return OrderStatus.FAILED
    # Commande comportant des éléments annulés : défini avec UC-15, hors Phase 1.
    raise InvalidItemTransition("État global non défini en Phase 1 pour ces éléments.")


@dataclass(frozen=True)
class NewOrderItem:
    """Élément validé par le service applicatif, prêt à entrer dans une commande."""

    action: OrderItemAction
    drone_id: DroneId
    service_type: str
    characteristics: CharacteristicSnapshot


class ServiceOrderItem:
    """Entité interne à l'agrégat : un couple (drone, type de service) et son état."""

    def __init__(
        self,
        *,
        id: OrderItemId,
        action: OrderItemAction,
        drone_id: DroneId,
        service_type: str,
        characteristics: CharacteristicSnapshot,
        status: ItemStatus,
        failure_cause: FailureCause | None = None,
    ) -> None:
        self._id = id
        self._action = action
        self._drone_id = drone_id
        self._service_type = service_type
        self._characteristics = characteristics
        self._status = status
        self._failure_cause = failure_cause

    @property
    def id(self) -> OrderItemId:
        return self._id

    @property
    def action(self) -> OrderItemAction:
        return self._action

    @property
    def drone_id(self) -> DroneId:
        return self._drone_id

    @property
    def service_type(self) -> str:
        return self._service_type

    @property
    def characteristics(self) -> CharacteristicSnapshot:
        return self._characteristics

    @property
    def status(self) -> ItemStatus:
        return self._status

    @property
    def failure_cause(self) -> FailureCause | None:
        return self._failure_cause

    def _move_to(self, target: ItemStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS.get(self._status, frozenset()):
            raise InvalidItemTransition(
                f"Transition interdite pour l'élément {self._id} : {self._status.value} -> {target.value}."
            )
        self._status = target

    def start(self) -> None:
        self._move_to(ItemStatus.IN_PROGRESS)

    def complete(self) -> None:
        self._move_to(ItemStatus.COMPLETED)

    def fail(self, cause: FailureCause) -> None:
        self._move_to(ItemStatus.FAILED)
        self._failure_cause = cause


class ServiceOrder:
    """Racine d'agrégat.

    Invariants : au moins un élément; aucun couple (drone, service) en double;
    caractéristiques figées; état global toujours dérivé des éléments.
    """

    def __init__(
        self,
        *,
        id: ServiceOrderId,
        client_id: ClientId,
        idempotency_key: IdempotencyKey,
        fingerprint: RequestFingerprint,
        correlation_id: CorrelationId,
        items: Sequence[ServiceOrderItem],
        created_at: datetime,
        version: int,
    ) -> None:
        if not items:
            raise EmptyOrder()
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.drone_id.value, item.service_type)
            if key in seen:
                raise DuplicateItem(*key)
            seen.add(key)
        self._id = id
        self._client_id = client_id
        self._idempotency_key = idempotency_key
        self._fingerprint = fingerprint
        self._correlation_id = correlation_id
        self._items = list(items)
        self._created_at = created_at
        self._version = version
        self._status = derive_order_status(i.status for i in self._items)

    @classmethod
    def create(
        cls,
        *,
        client_id: ClientId,
        idempotency_key: IdempotencyKey,
        fingerprint: RequestFingerprint,
        correlation_id: CorrelationId,
        items: Sequence[NewOrderItem],
        now: datetime,
    ) -> "ServiceOrder":
        return cls(
            id=ServiceOrderId.new(),
            client_id=client_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            correlation_id=correlation_id,
            items=[
                ServiceOrderItem(
                    id=OrderItemId.new(),
                    action=item.action,
                    drone_id=item.drone_id,
                    service_type=item.service_type,
                    characteristics=item.characteristics,
                    status=ItemStatus.RECEIVED,
                )
                for item in items
            ],
            created_at=now,
            version=0,
        )

    @classmethod
    def reconstitute(
        cls,
        *,
        id: ServiceOrderId,
        client_id: ClientId,
        idempotency_key: IdempotencyKey,
        fingerprint: RequestFingerprint,
        correlation_id: CorrelationId,
        items: Sequence[ServiceOrderItem],
        created_at: datetime,
        version: int,
    ) -> "ServiceOrder":
        # L'état global n'est pas relu : il est toujours recalculé à partir des éléments.
        return cls(
            id=id,
            client_id=client_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            correlation_id=correlation_id,
            items=items,
            created_at=created_at,
            version=version,
        )

    # --- Transitions (appelées par la simulation en Phase 1, par Activation en Phase 2)

    def item(self, item_id: OrderItemId) -> ServiceOrderItem:
        for candidate in self._items:
            if candidate.id == item_id:
                return candidate
        raise UnknownOrderItem(f"Élément {item_id} absent de la commande {self._id}.")

    def start_item(self, item_id: OrderItemId) -> None:
        self.item(item_id).start()
        self._recompute()

    def complete_item(self, item_id: OrderItemId) -> None:
        self.item(item_id).complete()
        self._recompute()

    def fail_item(self, item_id: OrderItemId, cause: FailureCause) -> None:
        self.item(item_id).fail(cause)
        self._recompute()

    def _recompute(self) -> None:
        self._status = derive_order_status(i.status for i in self._items)

    # --- Lecture

    def matches(self, fingerprint: RequestFingerprint) -> bool:
        return self._fingerprint == fingerprint

    @property
    def id(self) -> ServiceOrderId:
        return self._id

    @property
    def client_id(self) -> ClientId:
        return self._client_id

    @property
    def idempotency_key(self) -> IdempotencyKey:
        return self._idempotency_key

    @property
    def fingerprint(self) -> RequestFingerprint:
        return self._fingerprint

    @property
    def correlation_id(self) -> CorrelationId:
        return self._correlation_id

    @property
    def items(self) -> tuple[ServiceOrderItem, ...]:
        return tuple(self._items)

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def version(self) -> int:
        """Version lue en base, pour le verrouillage optimiste."""
        return self._version

    def __repr__(self) -> str:
        return f"ServiceOrder({self._id}, {self._status.value}, {len(self._items)} éléments)"
