"""Cas d'utilisation UC-04 : commander les services d'un drone."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Sequence

from candronex.audit.api import AuditLog, AuditRecord
from candronex.catalog.api import CatalogQueries
from candronex.fleet.api import FleetQueries
from candronex.ordering.application.ports import (
    ActivationRequest,
    ActivationRequester,
    OrderingUnitOfWorkFactory,
)
from candronex.ordering.domain.errors import (
    DroneNotEligible,
    DuplicateIdempotencyKey,
    EmptyOrder,
    IdempotencyKeyReused,
    UnknownServiceType,
    UnsupportedAction,
)
from candronex.ordering.domain.service_order import NewOrderItem, ServiceOrder
from candronex.ordering.domain.values import (
    Characteristic,
    CharacteristicSnapshot,
    IdempotencyKey,
    OrderItemAction,
    RequestFingerprint,
)
from candronex.shared.clock import Clock, utc_now
from candronex.shared.ids import ClientId, CorrelationId, DroneId

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderItemInput:
    action: str
    drone_id: str
    service_type: str


@dataclass(frozen=True)
class CreateServiceOrderCommand:
    client_id: ClientId
    idempotency_key: str
    items: tuple[OrderItemInput, ...]
    correlation_id: CorrelationId


@dataclass(frozen=True)
class CreateServiceOrderResult:
    order: ServiceOrder
    created: bool  # False lors d'un rejeu idempotent


def compute_fingerprint(items: Sequence[OrderItemInput]) -> RequestFingerprint:
    canonical = json.dumps(
        [{"action": i.action, "droneId": i.drone_id, "serviceType": i.service_type} for i in items],
        separators=(",", ":"),
        sort_keys=True,
    )
    return RequestFingerprint(hashlib.sha256(canonical.encode("utf-8")).hexdigest())


class CreateServiceOrderService:
    def __init__(
        self,
        uow_factory: OrderingUnitOfWorkFactory,
        fleet: FleetQueries,
        catalog: CatalogQueries,
        activation: ActivationRequester,
        audit_log: AuditLog,
        clock: Clock = utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._fleet = fleet
        self._catalog = catalog
        self._activation = activation
        self._audit_log = audit_log
        self._clock = clock

    def execute(self, command: CreateServiceOrderCommand) -> CreateServiceOrderResult:
        if not command.items:
            raise EmptyOrder()
        key = IdempotencyKey(command.idempotency_key)
        fingerprint = compute_fingerprint(command.items)

        # 1. Rejeu? (ADR-006)
        existing = self._find_existing(command.client_id, key)
        if existing is not None:
            return self._replay(existing, fingerprint, command)

        # 2. Lectures dans Fleet et Catalog, avant toute transaction.
        new_items = [self._prepare_item(command.client_id, item) for item in command.items]

        # 3. L'agrégat applique ses invariants et fige les caractéristiques.
        order = ServiceOrder.create(
            client_id=command.client_id,
            idempotency_key=key,
            fingerprint=fingerprint,
            correlation_id=command.correlation_id,
            items=new_items,
            now=self._clock(),
        )

        # 4. Une seule transaction, limitée aux données d'Ordering.
        try:
            with self._uow_factory() as uow:
                uow.orders.add(order)
                uow.commit()
        except DuplicateIdempotencyKey:
            # Requête identique simultanée : la contrainte d'unicité a désigné un gagnant.
            winner = self._find_existing(command.client_id, key)
            if winner is None:
                raise
            return self._replay(winner, fingerprint, command)

        # 5. Après validation seulement : demander l'activation de chaque élément.
        for item in order.items:
            self._activation.request_activation(
                ActivationRequest(
                    client_id=order.client_id.value,
                    order_id=str(order.id),
                    item_id=str(item.id),
                    drone_id=item.drone_id.value,
                    service_type=item.service_type,
                    characteristics=tuple(
                        (c.name, c.value) for c in item.characteristics.characteristics
                    ),
                    correlation_id=order.correlation_id.value,
                )
            )

        self._audit_log.record(
            AuditRecord(
                action="SERVICE_ORDER_CREATED",
                actor_id=command.client_id.value,
                resource_type="service_order",
                resource_id=str(order.id),
                correlation_id=command.correlation_id.value,
                details={"items": str(len(order.items))},
            )
        )
        log.info("[application] commande créée", extra={"fields": {"orderId": str(order.id)}})
        return CreateServiceOrderResult(order=order, created=True)

    def _find_existing(self, client_id: ClientId, key: IdempotencyKey) -> ServiceOrder | None:
        with self._uow_factory() as uow:
            return uow.orders.find_by_idempotency_key(client_id, key)

    def _replay(
        self,
        existing: ServiceOrder,
        fingerprint: RequestFingerprint,
        command: CreateServiceOrderCommand,
    ) -> CreateServiceOrderResult:
        if not existing.matches(fingerprint):
            raise IdempotencyKeyReused()
        self._audit_log.record(
            AuditRecord(
                action="SERVICE_ORDER_REPLAYED",
                actor_id=command.client_id.value,
                resource_type="service_order",
                resource_id=str(existing.id),
                correlation_id=command.correlation_id.value,
            )
        )
        log.info("[application] rejeu idempotent", extra={"fields": {"orderId": str(existing.id)}})
        return CreateServiceOrderResult(order=existing, created=False)

    def _prepare_item(self, client_id: ClientId, item: OrderItemInput) -> NewOrderItem:
        try:
            action = OrderItemAction(item.action)
        except ValueError:
            raise UnsupportedAction(item.action) from None

        drone = self._fleet.find_drone(client_id, item.drone_id)
        if drone is None or not drone.eligible_for_services:
            raise DroneNotEligible(item.drone_id)

        spec = self._catalog.find_specification(item.service_type)
        if spec is None:
            raise UnknownServiceType(item.service_type)

        return NewOrderItem(
            action=action,
            drone_id=DroneId(drone.drone_id),
            service_type=spec.service_type,
            characteristics=CharacteristicSnapshot(
                tuple(Characteristic(c.name, c.value) for c in spec.characteristics)
            ),
        )
