"""Doubles de test en mémoire, qui implémentent les mêmes ports que les adaptateurs réels.

Ils reproduisent les garanties de la base qui comptent pour les règles métier :
unicité, transaction (rien n'est visible avant commit) et verrouillage optimiste.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone

from candronex.audit.api import AuditRecord
from candronex.catalog.api import CharacteristicView, ServiceSpecificationView
from candronex.fleet.api import DroneSummary
from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.errors import DroneAlreadyRegistered, NetworkIdentityInUse
from candronex.fleet.domain.values import Iccid, Imsi
from candronex.identity.domain.b2b_client import ApiCredential, B2BClient
from candronex.ordering.application.ports import ActivationRequest
from candronex.ordering.domain.errors import (
    ConcurrentModification,
    DuplicateIdempotencyKey,
)
from candronex.ordering.domain.service_order import ServiceOrder
from candronex.ordering.domain.values import IdempotencyKey, ServiceOrderId
from candronex.shared.ids import ClientId, DroneId

FIXED_NOW = datetime(2026, 10, 4, 15, 30, tzinfo=timezone.utc)


def fixed_clock() -> datetime:
    return FIXED_NOW


# --------------------------------------------------------------------------- Audit
class RecordingAuditLog:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def record(self, record: AuditRecord) -> None:
        self.records.append(record)

    @property
    def actions(self) -> list[str]:
        return [r.action for r in self.records]


# --------------------------------------------------------------------------- Fleet
class InMemoryDroneStore:
    def __init__(self) -> None:
        self.drones: list[Drone] = []


class InMemoryDroneRepository:
    def __init__(self, store: InMemoryDroneStore, pending: list[Drone]) -> None:
        self._store = store
        self._pending = pending

    def exists(self, client_id: ClientId, drone_id: DroneId) -> bool:
        return self.find(client_id, drone_id) is not None

    def network_identity_in_use(self, imsi: Imsi, iccid: Iccid) -> bool:
        return any(d.imsi == imsi or d.sim.iccid == iccid for d in self._store.drones)

    def find(self, client_id: ClientId, drone_id: DroneId) -> Drone | None:
        return next(
            (d for d in self._store.drones if d.client_id == client_id and d.drone_id == drone_id),
            None,
        )

    def add(self, drone: Drone) -> None:
        self._pending.append(drone)


class InMemoryFleetUnitOfWork:
    def __init__(self, store: InMemoryDroneStore) -> None:
        self._store = store
        self._pending: list[Drone] = []
        self.committed = False

    def __enter__(self) -> "InMemoryFleetUnitOfWork":
        self.drones = InMemoryDroneRepository(self._store, self._pending)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._pending.clear()  # rollback

    def commit(self) -> None:
        # Mêmes garanties que les contraintes d'unicité de la base.
        for drone in self._pending:
            for other in self._store.drones:
                if other.client_id == drone.client_id and other.drone_id == drone.drone_id:
                    raise DroneAlreadyRegistered(drone.drone_id.value)
                if other.imsi == drone.imsi or other.sim.iccid == drone.sim.iccid:
                    raise NetworkIdentityInUse()
        self._store.drones.extend(self._pending)
        self._pending.clear()
        self.committed = True


class FakeFleetQueries:
    """FleetQueries simplifié : {(client, droneId): statut}."""

    def __init__(self, drones: dict[tuple[str, str], str] | None = None) -> None:
        self.drones = drones or {}

    def find_drone(self, client_id: ClientId, drone_id: str) -> DroneSummary | None:
        status = self.drones.get((client_id.value, drone_id))
        if status is None:
            return None
        return DroneSummary(
            drone_id=drone_id, status=status, eligible_for_services=status == "ACTIVE"
        )


# --------------------------------------------------------------------------- Catalog
REFERENCE_CATALOG = {
    "C2": ServiceSpecificationView(
        "C2",
        "C&C Connectivity",
        (
            CharacteristicView("sst", 2),
            CharacteristicView("sd", "000001"),
            CharacteristicView("dnn", "c2"),
            CharacteristicView("fiveQi", 7),
            CharacteristicView("arp", 2),
            CharacteristicView("ambrUplink", "20 Mbps"),
            CharacteristicView("ambrDownlink", "20 Mbps"),
        ),
    ),
    "IMAGERY": ServiceSpecificationView(
        "IMAGERY",
        "Imagery Connectivity",
        (
            CharacteristicView("sst", 1),
            CharacteristicView("sd", "000002"),
            CharacteristicView("dnn", "imagery"),
            CharacteristicView("fiveQi", 9),
            CharacteristicView("arp", 8),
            CharacteristicView("ambrUplink", "500 Mbps"),
            CharacteristicView("ambrDownlink", "100 Mbps"),
        ),
    ),
}


class FakeCatalogQueries:
    def __init__(self, specifications: dict[str, ServiceSpecificationView] | None = None) -> None:
        self.specifications = dict(REFERENCE_CATALOG if specifications is None else specifications)

    def find_specification(self, service_type: str) -> ServiceSpecificationView | None:
        return self.specifications.get(service_type)


# --------------------------------------------------------------------------- Ordering
@dataclass
class _StoredOrder:
    order: ServiceOrder
    version: int


@dataclass
class InMemoryOrderStore:
    orders: dict[str, _StoredOrder] = field(default_factory=dict)
    # Permet de simuler une requête concurrente qui gagne la course à l'insertion.
    hide_from_next_lookup: int = 0

    def snapshot(self, stored: _StoredOrder) -> ServiceOrder:
        order = copy.deepcopy(stored.order)
        order._version = stored.version  # ce que lirait le dépôt réel
        return order


class InMemoryServiceOrderRepository:
    def __init__(self, store: InMemoryOrderStore, staged: list[tuple[str, ServiceOrder]]) -> None:
        self._store = store
        self._staged = staged

    def add(self, order: ServiceOrder) -> None:
        self._staged.append(("add", order))

    def get(self, client_id: ClientId, order_id: ServiceOrderId) -> ServiceOrder | None:
        stored = self._store.orders.get(str(order_id))
        if stored is None or stored.order.client_id != client_id:
            return None
        return self._store.snapshot(stored)

    def find_by_idempotency_key(
        self, client_id: ClientId, key: IdempotencyKey
    ) -> ServiceOrder | None:
        if self._store.hide_from_next_lookup > 0:
            self._store.hide_from_next_lookup -= 1
            return None
        for stored in self._store.orders.values():
            if stored.order.client_id == client_id and stored.order.idempotency_key == key:
                return self._store.snapshot(stored)
        return None

    def update(self, order: ServiceOrder) -> None:
        self._staged.append(("update", order))


class InMemoryOrderingUnitOfWork:
    def __init__(self, store: InMemoryOrderStore) -> None:
        self._store = store
        self._staged: list[tuple[str, ServiceOrder]] = []

    def __enter__(self) -> "InMemoryOrderingUnitOfWork":
        self.orders = InMemoryServiceOrderRepository(self._store, self._staged)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._staged.clear()

    def commit(self) -> None:
        for kind, order in self._staged:
            if kind == "add":
                for stored in self._store.orders.values():
                    if (
                        stored.order.client_id == order.client_id
                        and stored.order.idempotency_key == order.idempotency_key
                    ):
                        raise DuplicateIdempotencyKey()
                self._store.orders[str(order.id)] = _StoredOrder(copy.deepcopy(order), version=1)
            else:
                stored = self._store.orders[str(order.id)]
                if stored.version != order.version:
                    raise ConcurrentModification()
                self._store.orders[str(order.id)] = _StoredOrder(
                    copy.deepcopy(order), version=stored.version + 1
                )
        self._staged.clear()


class RecordingActivationRequester:
    def __init__(self) -> None:
        self.requests: list[ActivationRequest] = []

    def request_activation(self, request: ActivationRequest) -> None:
        self.requests.append(request)


# --------------------------------------------------------------------------- Identity
class InMemoryIdentityUnitOfWork:
    def __init__(self, credentials: list[ApiCredential], clients: list[B2BClient]) -> None:
        self._credentials = credentials
        self._clients = clients

    def __enter__(self) -> "InMemoryIdentityUnitOfWork":
        outer = self

        class _Credentials:
            def find_by_token_hash(self, token_hash: str) -> ApiCredential | None:
                return next((c for c in outer._credentials if c.token_hash == token_hash), None)

        class _Clients:
            def find(self, client_id: ClientId) -> B2BClient | None:
                return next((c for c in outer._clients if c.client_id == client_id), None)

        self.credentials = _Credentials()
        self.clients = _Clients()
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def commit(self) -> None:
        pass
