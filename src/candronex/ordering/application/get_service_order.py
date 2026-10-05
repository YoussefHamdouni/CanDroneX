from __future__ import annotations

from candronex.ordering.application.ports import OrderingUnitOfWorkFactory
from candronex.ordering.domain.errors import ServiceOrderNotFound
from candronex.ordering.domain.service_order import ServiceOrder
from candronex.ordering.domain.values import ServiceOrderId
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId


class GetServiceOrderService:
    def __init__(self, uow_factory: OrderingUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, client_id: ClientId, order_id: str) -> ServiceOrder:
        try:
            parsed = ServiceOrderId.parse(order_id)
        except InvalidInput:
            raise ServiceOrderNotFound() from None
        with self._uow_factory() as uow:
            order = uow.orders.get(client_id, parsed)
        if order is None:  # inexistante ou appartenant à un autre client : même réponse
            raise ServiceOrderNotFound()
        return order
