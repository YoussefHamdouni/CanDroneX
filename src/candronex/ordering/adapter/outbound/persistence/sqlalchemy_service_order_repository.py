from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from candronex.ordering.adapter.outbound.persistence import mapper
from candronex.ordering.adapter.outbound.persistence.models import ServiceOrderModel
from candronex.ordering.domain.errors import (
    ConcurrentModification,
    DuplicateIdempotencyKey,
    DuplicateItem,
)
from candronex.ordering.domain.repository import ServiceOrderRepository
from candronex.ordering.domain.service_order import ServiceOrder
from candronex.ordering.domain.values import IdempotencyKey, ServiceOrderId
from candronex.platform.db import SessionFactory, constraint_name
from candronex.shared.clock import Clock, utc_now
from candronex.shared.ids import ClientId


class SqlAlchemyServiceOrderRepository:
    def __init__(self, session: Session, clock: Clock = utc_now) -> None:
        self._session = session
        self._clock = clock

    def add(self, order: ServiceOrder) -> None:
        self._session.add(mapper.to_model(order, self._clock()))

    def get(self, client_id: ClientId, order_id: ServiceOrderId) -> ServiceOrder | None:
        model = self._session.scalar(
            select(ServiceOrderModel).where(
                ServiceOrderModel.id == order_id.value,
                ServiceOrderModel.client_id == client_id.value,
            )
        )
        return None if model is None else mapper.to_domain(model)

    def find_by_idempotency_key(
        self, client_id: ClientId, key: IdempotencyKey
    ) -> ServiceOrder | None:
        model = self._session.scalar(
            select(ServiceOrderModel).where(
                ServiceOrderModel.client_id == client_id.value,
                ServiceOrderModel.idempotency_key == key.value,
            )
        )
        return None if model is None else mapper.to_domain(model)

    def update(self, order: ServiceOrder) -> None:
        model = self._session.get(ServiceOrderModel, order.id.value)
        if model is None or model.client_id != order.client_id.value:
            raise ConcurrentModification("Commande disparue entre la lecture et l'écriture.")
        if model.version != order.version:
            raise ConcurrentModification("La commande a été modifiée entre-temps.")
        mapper.apply_changes(order, model, self._clock())


class SqlAlchemyOrderingUnitOfWork:
    orders: ServiceOrderRepository

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyOrderingUnitOfWork":
        self._session = self._session_factory()
        self.orders = SqlAlchemyServiceOrderRepository(self._session)
        return self

    def __exit__(self, *exc_info: object) -> None:
        assert self._session is not None
        self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        assert self._session is not None
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            name = constraint_name(error)
            if name == "uq_service_order_client_idempotency_key":
                raise DuplicateIdempotencyKey() from error
            if name == "uq_service_order_item_drone_service":
                raise DuplicateItem() from error
            raise
        except StaleDataError as error:
            self._session.rollback()
            raise ConcurrentModification(str(error)) from error
