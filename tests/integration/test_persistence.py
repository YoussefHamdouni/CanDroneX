"""Dépôts SQLAlchemy sur PostgreSQL : aller-retour, contraintes, idempotence, concurrence."""

from __future__ import annotations

import threading

import pytest

from candronex.catalog.adapter.outbound.persistence.sqlalchemy_specification_repository import (
    SqlAlchemyCatalogUnitOfWork,
)
from candronex.catalog.application.catalog_queries import CatalogQueriesService
from candronex.fleet.adapter.outbound.persistence.sqlalchemy_drone_repository import (
    SqlAlchemyFleetUnitOfWork,
)
from candronex.fleet.application.fleet_queries import FleetQueriesService
from candronex.fleet.application.register_drone import (
    RegisterDroneCommand,
    RegisterDroneService,
)
from candronex.fleet.domain.errors import DroneAlreadyRegistered, NetworkIdentityInUse
from candronex.ordering.adapter.outbound.activation.simulated_activation_requester import (
    SimulatedActivationRequester,
    SimulationSettings,
)
from candronex.ordering.adapter.outbound.persistence.sqlalchemy_service_order_repository import (
    SqlAlchemyOrderingUnitOfWork,
)
from candronex.ordering.application.create_service_order import (
    CreateServiceOrderCommand,
    CreateServiceOrderService,
    OrderItemInput,
)
from candronex.ordering.domain.errors import ConcurrentModification
from candronex.ordering.domain.values import ItemStatus, OrderStatus
from candronex.shared.ids import ClientId, CorrelationId
from tests.unit.fakes import RecordingActivationRequester, RecordingAuditLog

pytestmark = pytest.mark.integration

CLIENT_1 = ClientId("CUSTOMER-001")
CLIENT_2 = ClientId("CUSTOMER-002")


def _register(
    session_factory,
    drone_id="DRN-0231",
    imsi="999700000010231",
    iccid="8999700000000102310",
    client=CLIENT_1,
):
    service = RegisterDroneService(
        lambda: SqlAlchemyFleetUnitOfWork(session_factory), RecordingAuditLog()
    )
    return service.execute(
        RegisterDroneCommand(client, drone_id, imsi, "ESIM", iccid, CorrelationId("it-corr"))
    )


def _ordering(session_factory, activation=None):
    activation = activation or RecordingActivationRequester()
    service = CreateServiceOrderService(
        lambda: SqlAlchemyOrderingUnitOfWork(session_factory),
        fleet=FleetQueriesService(lambda: SqlAlchemyFleetUnitOfWork(session_factory)),
        catalog=CatalogQueriesService(lambda: SqlAlchemyCatalogUnitOfWork(session_factory)),
        activation=activation,
        audit_log=RecordingAuditLog(),
    )
    return service, activation


def _command(key="it-key-1", client=CLIENT_1, drone="DRN-0231"):
    return CreateServiceOrderCommand(
        client_id=client,
        idempotency_key=key,
        items=(OrderItemInput("add", drone, "C2"), OrderItemInput("add", drone, "IMAGERY")),
        correlation_id=CorrelationId("it-corr"),
    )


def test_drone_aller_retour_et_contraintes_d_unicite(session_factory):
    _register(session_factory)
    queries = FleetQueriesService(lambda: SqlAlchemyFleetUnitOfWork(session_factory))
    assert queries.find_drone(CLIENT_1, "DRN-0231").eligible_for_services
    assert queries.find_drone(CLIENT_2, "DRN-0231") is None

    with pytest.raises(DroneAlreadyRegistered):
        _register(session_factory, imsi="999700000010232", iccid="8999700000000102320")
    with pytest.raises(NetworkIdentityInUse):
        _register(session_factory, drone_id="DRN-0232", iccid="8999700000000102320")


def test_la_contrainte_d_unicite_protege_contre_un_enregistrement_concurrent(session_factory):
    """Deux transactions vérifient en même temps que l'IMSI est libre; une seule peut valider."""
    from candronex.fleet.domain.drone import Drone
    from candronex.fleet.domain.values import Iccid, Imsi, SimInfo, SimType
    from candronex.shared.clock import utc_now
    from candronex.shared.ids import DroneId

    imsi = Imsi("999700000011000")

    def drone(drone_id, iccid):
        return Drone.register(
            client_id=CLIENT_1,
            drone_id=DroneId(drone_id),
            imsi=imsi,
            sim=SimInfo(SimType.ESIM, Iccid(iccid)),
            now=utc_now(),
        )

    with (
        SqlAlchemyFleetUnitOfWork(session_factory) as first,
        SqlAlchemyFleetUnitOfWork(session_factory) as second,
    ):
        a, b = drone("DRN-1000", "8999700000000110000"), drone("DRN-1001", "8999700000000110010")
        assert not first.drones.network_identity_in_use(a.imsi, a.sim.iccid)
        assert not second.drones.network_identity_in_use(b.imsi, b.sim.iccid)
        first.drones.add(a)
        first.commit()
        second.drones.add(b)
        with pytest.raises(NetworkIdentityInUse):
            second.commit()


def test_commande_aller_retour_avec_caracteristiques_figees(session_factory):
    _register(session_factory)
    service, activation = _ordering(session_factory)
    order = service.execute(_command()).order

    with SqlAlchemyOrderingUnitOfWork(session_factory) as uow:
        reloaded = uow.orders.get(CLIENT_1, order.id)
    assert reloaded is not None
    assert reloaded.status is OrderStatus.RECEIVED
    assert [i.service_type for i in reloaded.items] == ["C2", "IMAGERY"]
    c2 = dict((c.name, c.value) for c in reloaded.items[0].characteristics.characteristics)
    assert c2 == {
        "sst": 2,
        "sd": "000001",
        "dnn": "c2",
        "fiveQi": 7,
        "arp": 2,
        "ambrUplink": "20 Mbps",
        "ambrDownlink": "20 Mbps",
    }
    assert len(activation.requests) == 2

    with SqlAlchemyOrderingUnitOfWork(session_factory) as uow:
        assert uow.orders.get(CLIENT_2, order.id) is None  # isolation entre clients


def test_rejeu_et_requetes_simultanees_ne_creent_qu_une_commande(session_factory):
    _register(session_factory)
    service, _ = _ordering(session_factory)
    results = []

    def submit():
        results.append(service.execute(_command(key="it-concurrent")))

    threads = [threading.Thread(target=submit) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len({r.order.id for r in results}) == 1
    assert sum(r.created for r in results) == 1


def test_verrouillage_optimiste(session_factory):
    _register(session_factory)
    service, _ = _ordering(session_factory)
    order = service.execute(_command(key="it-lock")).order
    item_id = order.items[0].id

    with SqlAlchemyOrderingUnitOfWork(session_factory) as stale_uow:
        stale = stale_uow.orders.get(CLIENT_1, order.id)
        # Une autre transaction modifie la commande entre-temps.
        with SqlAlchemyOrderingUnitOfWork(session_factory) as other:
            fresh = other.orders.get(CLIENT_1, order.id)
            fresh.start_item(item_id)
            other.orders.update(fresh)
            other.commit()
        stale.start_item(item_id)
        with pytest.raises(ConcurrentModification):
            stale_uow.orders.update(stale)
            stale_uow.commit()


def test_simulation_complete_sur_base_reelle(session_factory):
    _register(session_factory)
    simulation = SimulatedActivationRequester(
        lambda: SqlAlchemyOrderingUnitOfWork(session_factory),
        RecordingAuditLog(),
        SimulationSettings(delay_seconds=0, failing_service_types=frozenset({"IMAGERY"})),
        sleep=lambda _: None,
    )
    service, _ = _ordering(session_factory, activation=simulation)
    order = service.execute(_command(key="it-sim")).order
    simulation.drain()

    with SqlAlchemyOrderingUnitOfWork(session_factory) as uow:
        stored = uow.orders.get(CLIENT_1, order.id)
    c2, imagery = stored.items
    assert c2.status is ItemStatus.COMPLETED
    assert imagery.status is ItemStatus.FAILED
    assert imagery.failure_cause.code == "SIMULATED_FAILURE"
    assert stored.status is OrderStatus.FAILED
