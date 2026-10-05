"""Règles métier de l'agrégat Drone et de ses objets valeur (UC-02)."""

import pytest

from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.values import DroneStatus, Iccid, Imsi, SimInfo, SimType
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId, DroneId
from tests.unit.fakes import FIXED_NOW


def _drone() -> Drone:
    return Drone.register(
        client_id=ClientId("CUSTOMER-001"),
        drone_id=DroneId("DRN-0231"),
        imsi=Imsi("999700000010231"),
        sim=SimInfo(SimType.ESIM, Iccid("8999700000000102310")),
        now=FIXED_NOW,
    )


def test_un_drone_enregistre_est_actif_et_peut_recevoir_des_services():
    drone = _drone()
    assert drone.status is DroneStatus.ACTIVE
    assert drone.can_receive_services
    assert drone.client_id == ClientId("CUSTOMER-001")


def test_un_drone_suspendu_ne_peut_pas_recevoir_de_services():
    drone = _drone()
    suspended = Drone.reconstitute(
        id=drone.id,
        client_id=drone.client_id,
        drone_id=drone.drone_id,
        imsi=drone.imsi,
        sim=drone.sim,
        status=DroneStatus.SUSPENDED,
        registered_at=drone.registered_at,
    )
    assert not suspended.can_receive_services


def test_l_imsi_doit_comporter_exactement_15_chiffres():
    for invalid in ["99970000001023", "9997000000102311", "99970000001023A", ""]:
        with pytest.raises(InvalidInput):
            Imsi(invalid)


def test_l_iccid_doit_comporter_19_ou_20_chiffres():
    Iccid("8999700000000102310")  # 19
    Iccid("89997000000001023101")  # 20
    for invalid in ["899970000000010231", "899970000000010231011", "8999700000000102A10"]:
        with pytest.raises(InvalidInput):
            Iccid(invalid)


def test_le_drone_id_respecte_son_format():
    DroneId("DRN-0231")
    for invalid in ["dr", "drn-0231", "DRN 0231", "X" * 33]:
        with pytest.raises(InvalidInput):
            DroneId(invalid)


def test_le_type_de_sim_doit_etre_connu():
    assert SimType.parse("ESIM") is SimType.ESIM
    with pytest.raises(InvalidInput):
        SimType.parse("USIM")


def test_l_imsi_n_apparait_jamais_en_clair_dans_une_representation():
    imsi = Imsi("999700000010231")
    assert imsi.masked() == "99970*******231"
    assert "999700000010231" not in repr(imsi)
    assert "999700000010231" not in str(imsi)
    assert "999700000010231" not in repr(_drone())
    assert "8999700000000102310" not in repr(Iccid("8999700000000102310"))
