from __future__ import annotations

from candronex.fleet.api import DroneSummary
from candronex.fleet.application.ports import FleetUnitOfWorkFactory
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId, DroneId


class FleetQueriesService:
    """Implémente FleetQueries (interface publiée du module)."""

    def __init__(self, uow_factory: FleetUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def find_drone(self, client_id: ClientId, drone_id: str) -> DroneSummary | None:
        try:
            parsed = DroneId(drone_id)
        except InvalidInput:
            return None  # un droneId mal formé ne peut désigner aucun drone
        with self._uow_factory() as uow:
            drone = uow.drones.find(client_id, parsed)
        if drone is None:
            return None
        return DroneSummary(
            drone_id=drone.drone_id.value,
            status=drone.status.value,
            eligible_for_services=drone.can_receive_services,
        )
