"""Configuration lue dans les variables d'environnement (voir .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(part.strip().upper() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_level: str = "INFO"
    simulation_delay_seconds: float = 3.0
    simulation_failing_service_types: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("La variable d'environnement DATABASE_URL est obligatoire.")
        return cls(
            database_url=database_url,
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            simulation_delay_seconds=float(os.environ.get("SIMULATION_DELAY_SECONDS", "3")),
            simulation_failing_service_types=_split_csv(
                os.environ.get("SIMULATION_FAILING_SERVICE_TYPES")
            ),
        )
