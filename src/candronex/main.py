"""Point d'entrée de l'application : `uvicorn candronex.main:create_app --factory`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from candronex.container import Container, build_container
from candronex.fleet.adapter.inbound.web.router import router as fleet_router
from candronex.ordering.adapter.inbound.web.router import router as ordering_router
from candronex.platform.config import Settings
from candronex.platform.logging_config import configure_logging
from candronex.platform.web.correlation import CorrelationIdMiddleware
from candronex.platform.web.errors import register_error_handlers
from candronex.platform.web.health import router as health_router


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.simulation.start()
        try:
            yield
        finally:
            container.simulation.stop()
            container.engine.dispose()

    app = FastAPI(
        title="CanDroneX",
        version="0.1.0",
        description="Plateforme B2B de connectivité 5G pour drones — Phase 1 (monolithe modulaire).",
        lifespan=lifespan,
    )
    app.state.engine = container.engine
    app.state.services = container.services
    app.state.client_authenticator = container.client_authenticator

    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(fleet_router)
    app.include_router(ordering_router)
    return app
