"""Service applicatif UC-02 : enregistrer un drone."""

import pytest

from candronex.fleet.application.fleet_queries import FleetQueriesService
from candronex.fleet.application.register_drone import (
    RegisterDroneCommand,
    RegisterDroneService,
)
from candronex.fleet.domain.errors import DroneAlreadyRegistered, NetworkIdentityInUse
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId, CorrelationId
from tests.unit.fakes import (
    InMemoryDroneStore,
    InMemoryFleetUnitOfWork,
    RecordingAuditLog,
    fixed_clock,
)

CLIENT_1 = ClientId("CUSTOMER-001")
CLIENT_2 = ClientId("CUSTOMER-002")


def _command(
    client=CLIENT_1,
    drone_id="DRN-0231",
    imsi="999700000010231",
    iccid="8999700000000102310",
    sim_type="ESIM",
):
    return RegisterDroneCommand(
        client_id=client,
        drone_id=drone_id,
        imsi=imsi,
        sim_type=sim_type,
        iccid=iccid,
        correlation_id=CorrelationId("corr-1"),
    )


def _service():
    store = InMemoryDroneStore()
    audit = RecordingAuditLog()
    service = RegisterDroneService(lambda: InMemoryFleetUnitOfWork(store), audit, fixed_clock)
    return service, store, audit


def test_accepte_l_enregistrement_d_un_drone_valide():
    service, store, audit = _service()

    result = service.execute(_command())

    assert result.drone_id == "DRN-0231"
    assert result.status == "ACTIVE"
    assert result.imsi_masked == "99970*******231"
    assert len(store.drones) == 1
    assert audit.actions == ["DRONE_REGISTERED"]
    assert "999700000010231" not in repr(audit.records)  # aucun IMSI dans l'audit


def test_refuse_un_drone_deja_enregistre_chez_le_meme_client():
    service, store, _ = _service()
    service.execute(_command())

    with pytest.raises(DroneAlreadyRegistered):
        service.execute(_command(imsi="999700000010232", iccid="8999700000000102320"))
    assert len(store.drones) == 1


def test_refuse_un_imsi_deja_associe_a_un_drone_d_un_autre_client():
    service, store, _ = _service()
    service.execute(_command())

    with pytest.raises(NetworkIdentityInUse) as error:
        service.execute(_command(client=CLIENT_2, drone_id="DRN-0999", iccid="8999700000000109990"))
    assert "CUSTOMER-001" not in error.value.detail  # ne révèle pas le propriétaire
    assert len(store.drones) == 1


def test_refuse_un_iccid_deja_utilise():
    service, _, _ = _service()
    service.execute(_command())
    with pytest.raises(NetworkIdentityInUse):
        service.execute(_command(drone_id="DRN-0232", imsi="999700000010232"))


def test_deux_clients_peuvent_utiliser_le_meme_drone_id():
    service, store, _ = _service()
    service.execute(_command())
    service.execute(_command(client=CLIENT_2, imsi="999700000020231", iccid="8999700000000202310"))
    assert len(store.drones) == 2


def test_refuse_des_informations_invalides_sans_rien_enregistrer():
    service, store, audit = _service()
    for command in [
        _command(imsi="12345"),
        _command(iccid="123"),
        _command(sim_type="USIM"),
        _command(drone_id="drn-0231"),
        _command(imsi=""),
    ]:
        with pytest.raises(InvalidInput):
            service.execute(command)
    assert store.drones == []
    assert audit.records == []


def test_fleet_queries_ne_revele_pas_les_drones_d_un_autre_client():
    service, store, _ = _service()
    service.execute(_command())
    queries = FleetQueriesService(lambda: InMemoryFleetUnitOfWork(store))

    own = queries.find_drone(CLIENT_1, "DRN-0231")
    assert own is not None and own.eligible_for_services
    assert queries.find_drone(CLIENT_2, "DRN-0231") is None
    assert queries.find_drone(CLIENT_1, "DRN-9999") is None
    assert queries.find_drone(CLIENT_1, "format invalide") is None
    assert not hasattr(own, "imsi")  # aucun identifiant d'abonné dans le DTO
