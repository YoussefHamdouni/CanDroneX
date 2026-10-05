"""Règles métier de l'agrégat ServiceOrder : invariants, transitions, état dérivé (§6.2)."""

from dataclasses import FrozenInstanceError

import pytest

from candronex.ordering.domain.errors import (
    DuplicateItem,
    EmptyOrder,
    InvalidItemTransition,
)
from candronex.ordering.domain.service_order import (
    NewOrderItem,
    ServiceOrder,
    derive_order_status,
)
from candronex.ordering.domain.values import (
    Characteristic,
    CharacteristicSnapshot,
    FailureCause,
    IdempotencyKey,
    ItemStatus,
    OrderItemAction,
    OrderStatus,
    RequestFingerprint,
)
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId, CorrelationId, DroneId
from tests.unit.fakes import FIXED_NOW

R, P, C, F = ItemStatus.RECEIVED, ItemStatus.IN_PROGRESS, ItemStatus.COMPLETED, ItemStatus.FAILED
CAUSE = FailureCause("SIMULATED_FAILURE", "échec")


def _item(service_type="C2", drone="DRN-0231"):
    return NewOrderItem(
        action=OrderItemAction.ADD,
        drone_id=DroneId(drone),
        service_type=service_type,
        characteristics=CharacteristicSnapshot(
            (Characteristic("sst", 2), Characteristic("dnn", "c2"))
        ),
    )


def _order(*items):
    return ServiceOrder.create(
        client_id=ClientId("CUSTOMER-001"),
        idempotency_key=IdempotencyKey("key-1"),
        fingerprint=RequestFingerprint("a" * 64),
        correlation_id=CorrelationId("corr-1"),
        items=list(items) or [_item("C2"), _item("IMAGERY")],
        now=FIXED_NOW,
    )


def test_une_commande_valide_a_un_element_par_service_et_est_recue():
    order = _order()
    assert order.status is OrderStatus.RECEIVED
    assert [i.service_type for i in order.items] == ["C2", "IMAGERY"]
    assert all(i.status is R for i in order.items)


def test_une_commande_doit_contenir_au_moins_un_element():
    with pytest.raises(EmptyOrder):
        ServiceOrder.create(
            client_id=ClientId("CUSTOMER-001"),
            idempotency_key=IdempotencyKey("key-1"),
            fingerprint=RequestFingerprint("a" * 64),
            correlation_id=CorrelationId("corr-1"),
            items=[],
            now=FIXED_NOW,
        )


def test_un_meme_service_ne_peut_pas_etre_commande_deux_fois_pour_un_drone():
    with pytest.raises(DuplicateItem):
        _order(_item("C2"), _item("C2"))
    _order(_item("C2", "DRN-0231"), _item("C2", "DRN-0232"))  # deux drones : permis


def test_les_caracteristiques_sont_figees():
    order = _order()
    snapshot = order.items[0].characteristics
    with pytest.raises(FrozenInstanceError):
        snapshot.characteristics = ()  # type: ignore[misc]
    assert snapshot.characteristics[0] == Characteristic("sst", 2)


def test_cycle_nominal_des_deux_elements():
    order = _order()
    c2, imagery = (i.id for i in order.items)

    order.start_item(c2)
    assert order.status is OrderStatus.IN_PROGRESS
    order.complete_item(c2)
    assert order.status is OrderStatus.IN_PROGRESS  # l'imagerie n'a pas encore d'issue
    order.start_item(imagery)
    order.complete_item(imagery)
    assert order.status is OrderStatus.COMPLETED


def test_un_echec_du_c2_n_est_jamais_masque_par_un_succes_de_l_imagerie():
    order = _order()
    c2, imagery = (i.id for i in order.items)
    order.start_item(c2)
    order.fail_item(c2, CAUSE)
    order.start_item(imagery)
    order.complete_item(imagery)

    assert order.status is OrderStatus.FAILED
    assert order.item(c2).status is F
    assert order.item(c2).failure_cause == CAUSE
    assert order.item(imagery).status is C


def test_les_transitions_interdites_sont_refusees():
    order = _order()
    c2 = order.items[0].id
    with pytest.raises(InvalidItemTransition):
        order.complete_item(c2)  # RECEIVED -> COMPLETED
    order.start_item(c2)
    order.complete_item(c2)
    with pytest.raises(InvalidItemTransition):
        order.fail_item(c2, CAUSE)  # COMPLETED -> FAILED
    with pytest.raises(InvalidItemTransition):
        order.start_item(c2)  # pas de retour en arrière


def test_regles_de_derivation_de_l_etat_global():
    cases = [
        ([R, R], OrderStatus.RECEIVED),
        ([P, R], OrderStatus.IN_PROGRESS),
        ([C, R], OrderStatus.IN_PROGRESS),
        ([C, P], OrderStatus.IN_PROGRESS),
        ([C, C], OrderStatus.COMPLETED),
        ([C, F], OrderStatus.FAILED),
        ([F, C], OrderStatus.FAILED),
        ([F, F], OrderStatus.FAILED),
    ]
    for statuses, expected in cases:
        assert derive_order_status(statuses) is expected, statuses


def test_la_cle_d_idempotence_est_validee():
    IdempotencyKey("7c9e6679-7425-40de-944b-e07fc1f90ae7")
    for invalid in ["", "avec espace", "x" * 256]:
        with pytest.raises(InvalidInput):
            IdempotencyKey(invalid)
