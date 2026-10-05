"""Cas d'utilisation UC-02 : enregistrer un drone et son identité réseau."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from candronex.audit.api import AuditLog, AuditRecord
from candronex.fleet.application.ports import FleetUnitOfWorkFactory
from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.errors import DroneAlreadyRegistered, NetworkIdentityInUse
from candronex.fleet.domain.values import Iccid, Imsi, SimInfo, SimType
from candronex.shared.clock import Clock, utc_now
from candronex.shared.ids import ClientId, CorrelationId, DroneId

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisterDroneCommand:
    client_id: ClientId
    drone_id: str
    imsi: str
    sim_type: str
    iccid: str
    correlation_id: CorrelationId


@dataclass(frozen=True)
class RegisteredDrone:
    drone_id: str
    status: str
    imsi_masked: str
    sim_type: str
    registered_at: datetime


class RegisterDroneService:
    def __init__(
        self,
        uow_factory: FleetUnitOfWorkFactory,
        audit_log: AuditLog,
        clock: Clock = utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._audit_log = audit_log
        self._clock = clock

    def execute(self, command: RegisterDroneCommand) -> RegisteredDrone:
        # Les objets valeur revalident le format, quelle que soit l'entrée.
        drone_id = DroneId(command.drone_id)
        imsi = Imsi(command.imsi)
        sim = SimInfo(SimType.parse(command.sim_type), Iccid(command.iccid))

        # Toutes les vérifications précèdent l'écriture : un refus ne modifie rien.
        with self._uow_factory() as uow:
            if uow.drones.exists(command.client_id, drone_id):
                raise DroneAlreadyRegistered(drone_id.value)
            if uow.drones.network_identity_in_use(imsi, sim.iccid):
                raise NetworkIdentityInUse()
            drone = Drone.register(
                client_id=command.client_id,
                drone_id=drone_id,
                imsi=imsi,
                sim=sim,
                now=self._clock(),
            )
            uow.drones.add(drone)
            uow.commit()  # contraintes d'unicité : protection contre la concurrence

        self._audit_log.record(
            AuditRecord(
                action="DRONE_REGISTERED",
                actor_id=command.client_id.value,
                resource_type="drone",
                resource_id=drone_id.value,
                correlation_id=command.correlation_id.value,
            )
        )
        log.info("[application] drone enregistré", extra={"fields": {"droneId": drone_id.value}})
        return RegisteredDrone(
            drone_id=drone.drone_id.value,
            status=drone.status.value,
            imsi_masked=drone.imsi.masked(),
            sim_type=drone.sim.sim_type.value,
            registered_at=drone.registered_at,
        )
