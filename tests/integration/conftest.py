"""Base PostgreSQL de test, migrée avec Alembic.

Deux modes, choisis automatiquement :
- dans le conteneur `app` (DATABASE_URL défini) : une base séparée `<base>_test` est créée
  sur le serveur PostgreSQL de Docker Compose, puis supprimée à la fin. Les données de
  l'application ne sont jamais touchées;
- sur le poste, sans DATABASE_URL : un conteneur PostgreSQL éphémère (testcontainers).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from candronex.platform.db import create_db_engine, create_session_factory

ROOT = Path(__file__).resolve().parents[2]


def _migrate(url: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(config, "head")


def _compose_test_database(app_url: str):
    """Crée une base de test séparée sur le serveur de l'application."""
    app = make_url(app_url)
    test_name = f"{app.database}_test"
    admin = create_engine(app.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{test_name}"'))
    test_url = app.set(database=test_name).render_as_string(hide_password=False)
    try:
        yield test_url
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
        admin.dispose()


def _ephemeral_container():
    testcontainers = pytest.importorskip("testcontainers.postgres")
    try:
        container = testcontainers.PostgresContainer("postgres:16-alpine", driver="psycopg")
        container.start()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Ni DATABASE_URL ni Docker disponibles : {error}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def database_url():
    app_url = os.environ.get("DATABASE_URL")
    source = _compose_test_database(app_url) if app_url else _ephemeral_container()
    url = next(source)
    _migrate(url)
    yield url
    source.close()  # exécute le bloc finally : suppression de la base ou du conteneur


@pytest.fixture(scope="session")
def engine(database_url):
    engine = create_db_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    yield create_session_factory(engine)
    # Nettoyage entre les tests : on conserve les données de démonstration (migration 0005).
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM ordering.service_order"))
        connection.execute(text("DELETE FROM fleet.drone WHERE drone_id <> 'DRN-0500'"))
