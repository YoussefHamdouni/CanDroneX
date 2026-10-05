"""Conversion entre l'agrégat Drone et son modèle SQLAlchemy (ADR-003)."""

from __future__ import annotations

from candronex.fleet.adapter.outbound.persistence.models import DroneModel
from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.values import DroneStatus, Iccid, Imsi, SimInfo, SimType
from candronex.shared.ids import ClientId, DroneId


def to_model(drone: Drone) -> DroneModel:
    return DroneModel(
        id=drone.id,
        client_id=drone.client_id.value,
        drone_id=drone.drone_id.value,
        imsi=drone.imsi.value,
        iccid=drone.sim.iccid.value,
        sim_type=drone.sim.sim_type.value,
        status=drone.status.value,
        registered_at=drone.registered_at,
    )


def to_domain(model: DroneModel) -> Drone:
    # reconstitute() revalide les objets valeur : une ligne incohérente est rejetée.
    return Drone.reconstitute(
        id=model.id,
        client_id=ClientId(model.client_id),
        drone_id=DroneId(model.drone_id),
        imsi=Imsi(model.imsi),
        sim=SimInfo(SimType(model.sim_type), Iccid(model.iccid)),
        status=DroneStatus(model.status),
        registered_at=model.registered_at,
    )
