"""Interface publiée du module Audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol


@dataclass(frozen=True)
class AuditRecord:
    """Qui a fait quoi, sur quelle ressource, avec quelle corrélation.

    Ne jamais y placer d'identifiant d'abonné en clair (IMSI, ICCID).
    """

    action: str
    actor_id: str
    resource_type: str
    resource_id: str
    correlation_id: str
    details: Mapping[str, str] = field(default_factory=dict)


class AuditLog(Protocol):
    def record(self, record: AuditRecord) -> None: ...
