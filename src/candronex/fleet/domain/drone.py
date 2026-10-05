"""Agrégat Drone."""

from __future__ import annotations

import uuid
from datetime import datetime

from candronex.fleet.domain.values import DroneStatus, Imsi, SimInfo
from candronex.shared.errors import InvalidInput
from candronex.shared.ids import ClientId, DroneId


class Drone:
    """Racine d'agrégat. Invariants : identité réseau valide, un seul client propriétaire.

    L'unicité de (client, droneId), de l'IMSI et de l'ICCID est garantie par le
    service applicatif et par les contraintes de la base (§8.1).
    """

    def __init__(
        self,
        *,
        id: uuid.UUID,
        client_id: ClientId,
        drone_id: DroneId,
        imsi: Imsi,
        sim: SimInfo,
        status: DroneStatus,
        registered_at: datetime,
    ) -> None:
        if registered_at.tzinfo is None:
            raise InvalidInput("La date d'enregistrement doit être horodatée (UTC).")
        self._id = id
        self._client_id = client_id
        self._drone_id = drone_id
        self._imsi = imsi
        self._sim = sim
        self._status = status
        self._registered_at = registered_at

    @classmethod
    def register(
        cls,
        *,
        client_id: ClientId,
        drone_id: DroneId,
        imsi: Imsi,
        sim: SimInfo,
        now: datetime,
    ) -> "Drone":
        return cls(
            id=uuid.uuid4(),
            client_id=client_id,
            drone_id=drone_id,
            imsi=imsi,
            sim=sim,
            status=DroneStatus.ACTIVE,
            registered_at=now,
        )

    @classmethod
    def reconstitute(
        cls,
        *,
        id: uuid.UUID,
        client_id: ClientId,
        drone_id: DroneId,
        imsi: Imsi,
        sim: SimInfo,
        status: DroneStatus,
        registered_at: datetime,
    ) -> "Drone":
        return cls(
            id=id,
            client_id=client_id,
            drone_id=drone_id,
            imsi=imsi,
            sim=sim,
            status=status,
            registered_at=registered_at,
        )

    @property
    def id(self) -> uuid.UUID:
        return self._id

    @property
    def client_id(self) -> ClientId:
        return self._client_id

    @property
    def drone_id(self) -> DroneId:
        return self._drone_id

    @property
    def imsi(self) -> Imsi:
        return self._imsi

    @property
    def sim(self) -> SimInfo:
        return self._sim

    @property
    def status(self) -> DroneStatus:
        return self._status

    @property
    def registered_at(self) -> datetime:
        return self._registered_at

    @property
    def can_receive_services(self) -> bool:
        return self._status is DroneStatus.ACTIVE

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Drone) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"Drone({self._client_id.value}/{self._drone_id.value}, {self._status.value})"
