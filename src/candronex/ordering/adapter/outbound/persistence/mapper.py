"""Conversion entre l'agrégat ServiceOrder et ses modèles SQLAlchemy (ADR-003)."""

from __future__ import annotations

from datetime import datetime

from candronex.ordering.adapter.outbound.persistence.models import (
    OrderItemCharacteristicModel,
    ServiceOrderItemModel,
    ServiceOrderModel,
)
from candronex.ordering.domain.service_order import ServiceOrder, ServiceOrderItem
from candronex.ordering.domain.values import (
    Characteristic,
    CharacteristicSnapshot,
    FailureCause,
    IdempotencyKey,
    ItemStatus,
    OrderItemAction,
    OrderItemId,
    RequestFingerprint,
    ServiceOrderId,
)
from candronex.shared.ids import ClientId, CorrelationId, DroneId


def _encode(value: int | str) -> tuple[str, str]:
    return (str(value), "int") if isinstance(value, int) else (value, "str")


def _decode(text: str, kind: str) -> int | str:
    return int(text) if kind == "int" else text


def to_model(order: ServiceOrder, now: datetime) -> ServiceOrderModel:
    model = ServiceOrderModel(
        id=order.id.value,
        client_id=order.client_id.value,
        idempotency_key=order.idempotency_key.value,
        request_fingerprint=order.fingerprint.value,
        correlation_id=order.correlation_id.value,
        status=order.status.value,
        created_at=order.created_at,
        updated_at=now,
    )
    for position, item in enumerate(order.items):
        item_model = ServiceOrderItemModel(
            id=item.id.value,
            position=position,
            action=item.action.value,
            drone_id=item.drone_id.value,
            service_type=item.service_type,
            status=item.status.value,
            failure_code=item.failure_cause.code if item.failure_cause else None,
            failure_message=item.failure_cause.message if item.failure_cause else None,
        )
        for char_position, characteristic in enumerate(item.characteristics.characteristics):
            text, kind = _encode(characteristic.value)
            item_model.characteristics.append(
                OrderItemCharacteristicModel(
                    name=characteristic.name,
                    value_text=text,
                    value_type=kind,
                    position=char_position,
                )
            )
        model.items.append(item_model)
    return model


def apply_changes(order: ServiceOrder, model: ServiceOrderModel, now: datetime) -> None:
    """Reporte les transitions d'état. Les éléments et caractéristiques ne changent jamais."""
    by_id = {item.id.value: item for item in order.items}
    for item_model in model.items:
        item = by_id[item_model.id]
        item_model.status = item.status.value
        item_model.failure_code = item.failure_cause.code if item.failure_cause else None
        item_model.failure_message = item.failure_cause.message if item.failure_cause else None
    model.status = order.status.value
    model.updated_at = now  # rend la ligne « modifiée » : la version est incrémentée


def to_domain(model: ServiceOrderModel) -> ServiceOrder:
    items = [
        ServiceOrderItem(
            id=OrderItemId(item.id),
            action=OrderItemAction(item.action),
            drone_id=DroneId(item.drone_id),
            service_type=item.service_type,
            characteristics=CharacteristicSnapshot(
                tuple(
                    Characteristic(c.name, _decode(c.value_text, c.value_type))
                    for c in item.characteristics
                )
            ),
            status=ItemStatus(item.status),
            failure_cause=(
                FailureCause(item.failure_code, item.failure_message or "")
                if item.failure_code
                else None
            ),
        )
        for item in model.items
    ]
    return ServiceOrder.reconstitute(
        id=ServiceOrderId(model.id),
        client_id=ClientId(model.client_id),
        idempotency_key=IdempotencyKey(model.idempotency_key),
        fingerprint=RequestFingerprint(model.request_fingerprint),
        correlation_id=CorrelationId(model.correlation_id),
        items=items,
        created_at=model.created_at,
        version=model.version,
    )
