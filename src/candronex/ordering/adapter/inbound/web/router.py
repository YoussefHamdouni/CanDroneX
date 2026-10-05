"""Adaptateur d'entrée REST du module Ordering. Aucune règle métier ici."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response, status

from candronex.ordering.adapter.inbound.web.schemas import (
    CharacteristicResponse,
    CreateServiceOrderRequest,
    FailureCauseResponse,
    OrderItemResponse,
    ServiceOrderResponse,
)
from candronex.ordering.application.create_service_order import (
    CreateServiceOrderCommand,
    CreateServiceOrderService,
    OrderItemInput,
)
from candronex.ordering.application.get_service_order import GetServiceOrderService
from candronex.ordering.domain.service_order import ServiceOrder
from candronex.platform.web.auth import get_client_id
from candronex.platform.web.correlation import correlation_id_of
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId

router = APIRouter(tags=["ordering"])


def to_response(order: ServiceOrder) -> ServiceOrderResponse:
    return ServiceOrderResponse(
        id=str(order.id),
        state=order.status.value,
        correlationId=order.correlation_id.value,
        createdAt=order.created_at,
        items=[
            OrderItemResponse(
                id=str(item.id),
                action=item.action.value,
                droneId=item.drone_id.value,
                serviceType=item.service_type,
                state=item.status.value,
                characteristics=[
                    CharacteristicResponse(name=c.name, value=c.value)
                    for c in item.characteristics.characteristics
                ],
                failureCause=(
                    FailureCauseResponse(
                        code=item.failure_cause.code, message=item.failure_cause.message
                    )
                    if item.failure_cause
                    else None
                ),
            )
            for item in order.items
        ],
    )


@router.post(
    "/service-orders",
    status_code=status.HTTP_201_CREATED,
    response_model=ServiceOrderResponse,
    responses={200: {"description": "Rejeu idempotent : commande existante"}},
)
def create_service_order(
    body: CreateServiceOrderRequest,
    request: Request,
    response: Response,
    client_id: ClientId = Depends(get_client_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ServiceOrderResponse:
    if not idempotency_key:
        raise InvalidInput(
            "L'en-tête Idempotency-Key est obligatoire.", code="IDEMPOTENCY_KEY_REQUIRED"
        )
    service: CreateServiceOrderService = request.app.state.services.create_service_order
    result = service.execute(
        CreateServiceOrderCommand(
            client_id=client_id,
            idempotency_key=idempotency_key,
            items=tuple(
                OrderItemInput(action=i.action, drone_id=i.droneId, service_type=i.serviceType)
                for i in body.items
            ),
            correlation_id=correlation_id_of(request),
        )
    )
    response.headers["Location"] = f"/service-orders/{result.order.id}"
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return to_response(result.order)


@router.get("/service-orders/{order_id}", response_model=ServiceOrderResponse)
def get_service_order(
    order_id: str,
    request: Request,
    client_id: ClientId = Depends(get_client_id),
) -> ServiceOrderResponse:
    service: GetServiceOrderService = request.app.state.services.get_service_order
    return to_response(service.execute(client_id, order_id))
