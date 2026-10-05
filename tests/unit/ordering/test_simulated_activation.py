"""Simulation du cycle de vie en Phase 1 (§6.2, ADR-005)."""

from candronex.ordering.adapter.outbound.activation.simulated_activation_requester import (
    SimulatedActivationRequester,
    SimulationSettings,
)
from candronex.ordering.domain.values import ItemStatus, OrderStatus
from tests.unit.fakes import InMemoryOrderingUnitOfWork
from tests.unit.ordering.test_create_service_order import Setup


def _simulation(setup, failing=frozenset()):
    return SimulatedActivationRequester(
        lambda: InMemoryOrderingUnitOfWork(setup.store),
        setup.audit,
        SimulationSettings(delay_seconds=0, failing_service_types=frozenset(failing)),
        sleep=lambda _: None,
    )


def _current(setup, order_id):
    return setup.store.orders[str(order_id)].order


def test_les_deux_services_reussissent():
    s = Setup()
    order = s.create().order
    simulation = _simulation(s)
    for request in s.activation.requests:
        simulation.process(request)

    stored = _current(s, order.id)
    assert stored.status is OrderStatus.COMPLETED
    assert all(i.status is ItemStatus.COMPLETED for i in stored.items)
    assert s.audit.actions.count("ORDER_ITEM_COMPLETED") == 2


def test_echec_simule_de_l_imagerie_commande_failed_et_c2_completed():
    s = Setup()
    order = s.create().order
    simulation = _simulation(s, failing={"IMAGERY"})
    for request in s.activation.requests:
        simulation.process(request)

    stored = _current(s, order.id)
    c2, imagery = stored.items
    assert c2.status is ItemStatus.COMPLETED
    assert imagery.status is ItemStatus.FAILED
    assert imagery.failure_cause.code == "SIMULATED_FAILURE"
    assert stored.status is OrderStatus.FAILED


def test_une_demande_repetee_ne_fait_pas_revenir_un_element_en_arriere():
    s = Setup()
    order = s.create().order
    simulation = _simulation(s)
    first = s.activation.requests[0]
    simulation.process(first)
    simulation.process(first)  # répétée : ignorée

    assert _current(s, order.id).items[0].status is ItemStatus.COMPLETED
    assert s.audit.actions.count("ORDER_ITEM_COMPLETED") == 1


def test_la_file_d_attente_traite_les_demandes_une_a_une():
    s = Setup()
    order = s.create().order
    simulation = _simulation(s)
    for request in s.activation.requests:
        simulation.request_activation(request)  # retour immédiat
    assert _current(s, order.id).status is OrderStatus.RECEIVED

    simulation.drain()
    assert _current(s, order.id).status is OrderStatus.COMPLETED
