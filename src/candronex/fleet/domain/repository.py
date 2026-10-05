from __future__ import annotations

from typing import Protocol

from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.values import Iccid, Imsi
from candronex.shared.ids import ClientId, DroneId


class DroneRepository(Protocol):
    def exists(self, client_id: ClientId, drone_id: DroneId) -> bool: ...

    def network_identity_in_use(self, imsi: Imsi, iccid: Iccid) -> bool:
        """Vérification d'unicité globale. Ne retourne qu'un booléen, aucune donnée d'un client."""
        ...

    def find(self, client_id: ClientId, drone_id: DroneId) -> Drone | None: ...

    def add(self, drone: Drone) -> None: ...
