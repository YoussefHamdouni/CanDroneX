from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from candronex.fleet.adapter.outbound.persistence import mapper
from candronex.fleet.adapter.outbound.persistence.models import DroneModel
from candronex.fleet.domain.drone import Drone
from candronex.fleet.domain.errors import DroneAlreadyRegistered, NetworkIdentityInUse
from candronex.fleet.domain.repository import DroneRepository
from candronex.fleet.domain.values import Iccid, Imsi
from candronex.platform.db import SessionFactory, constraint_name
from candronex.shared.ids import ClientId, DroneId


class SqlAlchemyDroneRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists(self, client_id: ClientId, drone_id: DroneId) -> bool:
        found = self._session.scalar(
            select(DroneModel.id)
            .where(DroneModel.client_id == client_id.value, DroneModel.drone_id == drone_id.value)
            .limit(1)
        )
        return found is not None

    def network_identity_in_use(self, imsi: Imsi, iccid: Iccid) -> bool:
        found = self._session.scalar(
            select(DroneModel.id)
            .where(or_(DroneModel.imsi == imsi.value, DroneModel.iccid == iccid.value))
            .limit(1)
        )
        return found is not None

    def find(self, client_id: ClientId, drone_id: DroneId) -> Drone | None:
        model = self._session.scalar(
            select(DroneModel).where(
                DroneModel.client_id == client_id.value, DroneModel.drone_id == drone_id.value
            )
        )
        return None if model is None else mapper.to_domain(model)

    def add(self, drone: Drone) -> None:
        self._session.add(mapper.to_model(drone))


class SqlAlchemyFleetUnitOfWork:
    drones: DroneRepository

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyFleetUnitOfWork":
        self._session = self._session_factory()
        self.drones = SqlAlchemyDroneRepository(self._session)
        return self

    def __exit__(self, *exc_info: object) -> None:
        assert self._session is not None
        self._session.rollback()  # sans effet si la transaction a déjà été validée
        self._session.close()

    def commit(self) -> None:
        assert self._session is not None
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            name = constraint_name(error)
            if name == "uq_drone_client_drone_id":
                raise DroneAlreadyRegistered() from error
            if name in {"uq_drone_imsi", "uq_drone_iccid"}:
                raise NetworkIdentityInUse() from error
            raise
