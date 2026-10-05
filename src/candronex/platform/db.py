"""Accès à la base de données : moteur, fabrique de sessions, outils d'erreur."""

from __future__ import annotations

from typing import TypeAlias

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

SessionFactory: TypeAlias = "sessionmaker[Session]"


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> SessionFactory:
    # expire_on_commit=False : les objets restent lisibles après la validation.
    return sessionmaker(bind=engine, expire_on_commit=False)


def constraint_name(error: IntegrityError) -> str | None:
    """Nom de la contrainte violée, fourni par le pilote PostgreSQL (psycopg)."""
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def database_is_up(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — toute erreur signifie « indisponible »
        return False
