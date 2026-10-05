"""Service applicatif UC-04 : commander les services d'un drone, avec idempotence."""

import pytest

from candronex.ordering.application.create_service_order import (
    CreateServiceOrderCommand,
    CreateServiceOrderService,
    OrderItemInput,
)
from candronex.ordering.application.get_service_order import GetServiceOrderService
from candronex.ordering.domain.errors import (
    DroneNotEligible,
    DuplicateItem,
    EmptyOrder,
    IdempotencyKeyReused,
    ServiceOrderNotFound,
    UnknownServiceType,
    UnsupportedAction,
)
from candronex.ordering.domain.values import Characteristic, OrderStatus
from candronex.shared.ids import ClientId, CorrelationId
from tests.unit.fakes import (
    FakeCatalogQueries,
    FakeFleetQueries,
    InMemoryOrderingUnitOfWork,
    InMemoryOrderStore,
    RecordingActivationRequester,
    RecordingAuditLog,
    fixed_clock,
)

CLIENT_1 = ClientId("CUSTOMER-001")
CLIENT_2 = ClientId("CUSTOMER-002")
BOTH = (
    OrderItemInput("add", "DRN-0231", "C2"),
    OrderItemInput("add", "DRN-0231", "IMAGERY"),
)


class Setup:
    def __init__(self) -> None:
        self.store = InMemoryOrderStore()
        self.fleet = FakeFleetQueries(
            {
                ("CUSTOMER-001", "DRN-0231"): "ACTIVE",
                ("CUSTOMER-001", "DRN-0777"): "SUSPENDED",
                ("CUSTOMER-002", "DRN-0500"): "ACTIVE",
            }
        )
        self.activation = RecordingActivationRequester()
        self.audit = RecordingAuditLog()
        self.service = CreateServiceOrderService(
            lambda: InMemoryOrderingUnitOfWork(self.store),
            fleet=self.fleet,
            catalog=FakeCatalogQueries(),
            activation=self.activation,
            audit_log=self.audit,
            clock=fixed_clock,
        )

    def create(self, items=BOTH, key="key-1", client=CLIENT_1):
        return self.service.execute(
            CreateServiceOrderCommand(
                client_id=client,
                idempotency_key=key,
                items=tuple(items),
                correlation_id=CorrelationId("corr-1"),
            )
        )


def test_accepte_une_commande_valide_pour_un_drone_enregistre():
    s = Setup()
    result = s.create()

    assert result.created
    order = result.order
    assert order.status is OrderStatus.RECEIVED
    assert len(order.items) == 2
    assert len(s.store.orders) == 1
    assert [r.service_type for r in s.activation.requests] == ["C2", "IMAGERY"]
    assert s.audit.actions == ["SERVICE_ORDER_CREATED"]


def test_les_caracteristiques_sont_copiees_du_catalogue():
    s = Setup()
    c2 = s.create().order.items[0]
    assert Characteristic("sst", 2) in c2.characteristics.characteristics
    assert Characteristic("arp", 2) in c2.characteristics.characteristics
    assert Characteristic("ambrUplink", "20 Mbps") in c2.characteristics.characteristics


def test_un_rejeu_identique_renvoie_la_commande_existante_sans_rien_creer():
    s = Setup()
    first = s.create()
    replay = s.create()

    assert not replay.created
    assert replay.order.id == first.order.id
    assert len(s.store.orders) == 1
    assert len(s.activation.requests) == 2  # aucune activation supplémentaire
    assert s.audit.actions == ["SERVICE_ORDER_CREATED", "SERVICE_ORDER_REPLAYED"]


def test_une_cle_reutilisee_avec_un_contenu_different_est_refusee():
    s = Setup()
    s.create()
    with pytest.raises(IdempotencyKeyReused):
        s.create(items=BOTH[:1])
    assert len(s.store.orders) == 1


def test_la_meme_cle_chez_deux_clients_ne_cree_pas_de_conflit():
    s = Setup()
    s.create()
    s.create(items=[OrderItemInput("add", "DRN-0500", "C2")], client=CLIENT_2)
    assert len(s.store.orders) == 2


def test_requete_identique_simultanee_une_seule_commande_est_creee():
    s = Setup()
    winner = s.create()
    # La seconde requête ne voit pas encore la commande, puis perd la course à l'insertion.
    s.store.hide_from_next_lookup = 1
    loser = s.create()

    assert not loser.created
    assert loser.order.id == winner.order.id
    assert len(s.store.orders) == 1
    assert len(s.activation.requests) == 2


def test_refuse_un_drone_inexistant_d_un_autre_client_ou_suspendu_sans_rien_enregistrer():
    s = Setup()
    for drone_id in ["DRN-9999", "DRN-0500", "DRN-0777"]:
        with pytest.raises(DroneNotEligible):
            s.create(items=[OrderItemInput("add", drone_id, "C2")], key=f"k-{drone_id}")
    assert s.store.orders == {}
    assert s.activation.requests == []


def test_refuse_un_type_de_service_absent_du_catalogue():
    s = Setup()
    with pytest.raises(UnknownServiceType):
        s.create(items=[OrderItemInput("add", "DRN-0231", "VIDEO_4K")])
    assert s.store.orders == {}


def test_refuse_une_action_autre_que_add():
    s = Setup()
    with pytest.raises(UnsupportedAction):
        s.create(items=[OrderItemInput("delete", "DRN-0231", "C2")])


def test_refuse_un_element_en_double():
    s = Setup()
    with pytest.raises(DuplicateItem):
        s.create(items=[BOTH[0], BOTH[0]])
    assert s.store.orders == {}


def test_refuse_une_commande_vide():
    s = Setup()
    with pytest.raises(EmptyOrder):
        s.create(items=[])


def test_un_client_ne_peut_pas_consulter_la_commande_d_un_autre():
    s = Setup()
    order = s.create().order
    queries = GetServiceOrderService(lambda: InMemoryOrderingUnitOfWork(s.store))

    assert queries.execute(CLIENT_1, str(order.id)).id == order.id
    with pytest.raises(ServiceOrderNotFound):
        queries.execute(CLIENT_2, str(order.id))
    with pytest.raises(ServiceOrderNotFound):
        queries.execute(CLIENT_1, "pas-un-uuid")
