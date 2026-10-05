"""Simulation du cycle de vie des éléments de commande (Phase 1, §6.2, ADR-005).

Aucun appel réseau : cet adaptateur fait évoluer l'état des éléments en arrière-plan,
une demande à la fois, selon un délai et une règle d'échec configurables. En Phase 2,
le module Activation implémentera le même port ActivationRequester.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from candronex.audit.api import AuditLog, AuditRecord
from candronex.ordering.application.ports import (
    ActivationRequest,
    OrderingUnitOfWorkFactory,
)
from candronex.ordering.domain.errors import ConcurrentModification
from candronex.ordering.domain.service_order import ServiceOrder
from candronex.ordering.domain.values import (
    FailureCause,
    ItemStatus,
    OrderItemId,
    ServiceOrderId,
)
from candronex.shared.ids import ClientId

log = logging.getLogger(__name__)

SIMULATED_FAILURE = FailureCause(
    code="SIMULATED_FAILURE",
    message="Échec d'activation simulé (règle de simulation configurée, Phase 1).",
)
_MAX_ATTEMPTS = 3
_STOP = object()


@dataclass(frozen=True)
class SimulationSettings:
    delay_seconds: float = 3.0
    failing_service_types: frozenset[str] = field(default_factory=frozenset)


class SimulatedActivationRequester:
    def __init__(
        self,
        uow_factory: OrderingUnitOfWorkFactory,
        audit_log: AuditLog,
        settings: SimulationSettings,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._uow_factory = uow_factory
        self._audit_log = audit_log
        self._settings = settings
        self._sleep = sleep
        self._queue: "queue.Queue[object]" = queue.Queue()
        self._worker: threading.Thread | None = None

    # --- Port ActivationRequester ------------------------------------------------

    def request_activation(self, request: ActivationRequest) -> None:
        """Retour immédiat : la demande est traitée plus tard, en arrière-plan."""
        self._queue.put(request)

    # --- Cycle de vie du travailleur ----------------------------------------------

    def start(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(
                target=self._run, name="activation-simulation", daemon=True
            )
            self._worker.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self._worker is not None:
            self._queue.put(_STOP)
            self._worker.join(timeout)
            self._worker = None

    def drain(self) -> None:
        """Traite immédiatement toutes les demandes en attente (utile aux tests)."""
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if item is not _STOP:
                self.process(item)  # type: ignore[arg-type]

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            try:
                self.process(item)  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001 — le travailleur ne doit jamais s'arrêter
                log.exception("[simulation] échec du traitement d'une demande d'activation")

    # --- Traitement d'une demande -------------------------------------------------

    def process(self, request: ActivationRequest) -> None:
        """RECEIVED -> IN_PROGRESS, puis COMPLETED ou FAILED selon la règle configurée."""
        self._sleep(self._settings.delay_seconds)
        if not self._apply(request, expected=ItemStatus.RECEIVED, transition=self._start):
            return
        self._sleep(self._settings.delay_seconds)
        if request.service_type.upper() in self._settings.failing_service_types:
            self._apply(request, expected=ItemStatus.IN_PROGRESS, transition=self._fail)
        else:
            self._apply(request, expected=ItemStatus.IN_PROGRESS, transition=self._complete)

    @staticmethod
    def _start(order: ServiceOrder, item_id: OrderItemId) -> None:
        order.start_item(item_id)

    @staticmethod
    def _complete(order: ServiceOrder, item_id: OrderItemId) -> None:
        order.complete_item(item_id)

    @staticmethod
    def _fail(order: ServiceOrder, item_id: OrderItemId) -> None:
        order.fail_item(item_id, SIMULATED_FAILURE)

    def _apply(
        self,
        request: ActivationRequest,
        *,
        expected: ItemStatus,
        transition: Callable[[ServiceOrder, OrderItemId], None],
    ) -> bool:
        client_id = ClientId(request.client_id)
        order_id = ServiceOrderId.parse(request.order_id)
        item_id = OrderItemId.parse(request.item_id)

        new_status: ItemStatus | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                with self._uow_factory() as uow:
                    order = uow.orders.get(client_id, order_id)
                    if order is None:
                        log.warning("[simulation] commande introuvable, demande ignorée")
                        return False
                    item = order.item(item_id)
                    if item.status is not expected:
                        # Idempotence des transitions : une demande répétée ne fait jamais
                        # revenir un élément en arrière.
                        log.info(
                            "[simulation] transition ignorée",
                            extra={
                                "fields": {"itemId": request.item_id, "status": item.status.value}
                            },
                        )
                        return False
                    transition(order, item_id)
                    uow.orders.update(order)
                    uow.commit()
                    new_status = order.item(item_id).status
                break
            except ConcurrentModification:
                log.info("[simulation] conflit de version, nouvelle tentative %d", attempt)
                if attempt == _MAX_ATTEMPTS:
                    raise
        if new_status is None:  # pragma: no cover — toutes les tentatives ont échoué
            return False
        self._audit_log.record(
            AuditRecord(
                action=f"ORDER_ITEM_{new_status.value}",
                actor_id="activation-simulation",
                resource_type="service_order_item",
                resource_id=request.item_id,
                correlation_id=request.correlation_id,
                details={"orderId": request.order_id, "serviceType": request.service_type},
            )
        )
        return True
