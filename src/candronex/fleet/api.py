"""Interface publiée du module Fleet.

Aucun identifiant d'abonné (IMSI, ICCID) ne sort du module par cette interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from candronex.shared.ids import ClientId


@dataclass(frozen=True)
class DroneSummary:
    drone_id: str
    status: str
    eligible_for_services: bool


class FleetQueries(Protocol):
    def find_drone(self, client_id: ClientId, drone_id: str) -> DroneSummary | None:
        """Retourne le drone du client, ou None s'il n'existe pas ou appartient à un autre client."""
        ...
