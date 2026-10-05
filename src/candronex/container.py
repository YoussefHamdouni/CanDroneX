"""Racine de composition : relie chaque port à son adaptateur.

C'est le seul endroit, avec main.py, autorisé à connaître tous les modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from candronex.audit.adapter.outbound.log.structured_log_audit_log import (
    StructuredLogAuditLog,
)
from candronex.catalog.adapter.outbound.persistence.sqlalchemy_specification_repository import (
    SqlAlchemyCatalogUnitOfWork,
)
from candronex.catalog.application.catalog_queries import CatalogQueriesService
from candronex.fleet.adapter.outbound.persistence.sqlalchemy_drone_repository import (
    SqlAlchemyFleetUnitOfWork,
)
from candronex.fleet.application.fleet_queries import FleetQueriesService
from candronex.fleet.application.register_drone import RegisterDroneService
from candronex.identity.adapter.outbound.persistence.sqlalchemy_identity_repository import (
    SqlAlchemyIdentityUnitOfWork,
)
from candronex.identity.application.authenticate_client import (
    ClientAuthenticationService,
)
from candronex.ordering.adapter.outbound.activation.simulated_activation_requester import (
    SimulatedActivationRequester,
    SimulationSettings,
)
from candronex.ordering.adapter.outbound.persistence.sqlalchemy_service_order_repository import (
    SqlAlchemyOrderingUnitOfWork,
)
from candronex.ordering.application.create_service_order import (
    CreateServiceOrderService,
)
from candronex.ordering.application.get_service_order import GetServiceOrderService
from candronex.platform.config import Settings
from candronex.platform.db import create_db_engine, create_session_factory


@dataclass(frozen=True)
class Services:
    register_drone: RegisterDroneService
    create_service_order: CreateServiceOrderService
    get_service_order: GetServiceOrderService


@dataclass(frozen=True)
class Container:
    engine: Engine
    services: Services
    client_authenticator: ClientAuthenticationService
    simulation: SimulatedActivationRequester


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    audit_log = StructuredLogAuditLog()

    def identity_uow() -> SqlAlchemyIdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(session_factory)

    def fleet_uow() -> SqlAlchemyFleetUnitOfWork:
        return SqlAlchemyFleetUnitOfWork(session_factory)

    def catalog_uow() -> SqlAlchemyCatalogUnitOfWork:
        return SqlAlchemyCatalogUnitOfWork(session_factory)

    def ordering_uow() -> SqlAlchemyOrderingUnitOfWork:
        return SqlAlchemyOrderingUnitOfWork(session_factory)

    simulation = SimulatedActivationRequester(
        ordering_uow,
        audit_log,
        SimulationSettings(
            delay_seconds=settings.simulation_delay_seconds,
            failing_service_types=settings.simulation_failing_service_types,
        ),
    )
    services = Services(
        register_drone=RegisterDroneService(fleet_uow, audit_log),
        create_service_order=CreateServiceOrderService(
            ordering_uow,
            fleet=FleetQueriesService(fleet_uow),
            catalog=CatalogQueriesService(catalog_uow),
            activation=simulation,
            audit_log=audit_log,
        ),
        get_service_order=GetServiceOrderService(ordering_uow),
    )
    return Container(
        engine=engine,
        services=services,
        client_authenticator=ClientAuthenticationService(identity_uow, audit_log),
        simulation=simulation,
    )
