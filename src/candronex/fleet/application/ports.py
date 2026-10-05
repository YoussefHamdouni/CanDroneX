from __future__ import annotations

from typing import Callable, Protocol

from candronex.fleet.domain.repository import DroneRepository


class FleetUnitOfWork(Protocol):
    drones: DroneRepository

    def __enter__(self) -> "FleetUnitOfWork": ...
    def __exit__(self, *exc_info: object) -> None: ...

    def commit(self) -> None:
        """Valide la transaction. Traduit une violation d'unicité en erreur métier."""
        ...


FleetUnitOfWorkFactory = Callable[[], FleetUnitOfWork]
